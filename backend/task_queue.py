"""arq task queue wiring (Phase 0 — Foundations).

One image, three roles (see ``config.worker_role``):
  * ``web``       — FastAPI; creates an arq pool on ``app.state.arq`` to enqueue.
  * ``scheduler`` — APScheduler (enqueue-only) + arq pool.
  * ``worker``    — runs ``arq worker.WorkerSettings`` and executes tasks.

Durability model (D9-A: persistent, non-evicting Redis):
  * Inbound webhooks are persisted to ``webhook_events`` before enqueue, then
    processed by the ``process_*`` tasks which flip ``status`` pending → processing
    → done/failed.
  * Outbound integration calls (Twilio / Resend / GBP / Square / DataForSEO) run
    through durable wrapper tasks with retry; exhausted retries land in
    ``dead_letter`` via :func:`record_dead_letter`.
  * :func:`reconcile_pending_webhooks` (arq cron, every 5 min) re-enqueues rows
    stuck ``pending`` — the backstop when Redis was briefly unavailable at enqueue.

The wrapper tasks are DEFINED here in Phase 0; each call site is migrated to
enqueue in its owning phase (see the master plan ownership map).
"""
import logging
from datetime import datetime, timezone
from typing import Any

from arq import cron, create_pool
from arq.connections import RedisSettings

from config import settings
from db import get_db

logger = logging.getLogger(__name__)

# Retry / timeout policy (shared by WorkerSettings and the dead-letter check).
MAX_TRIES = 5
JOB_TIMEOUT = 120  # seconds
KEEP_RESULT = 3600  # seconds


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def get_arq_pool():
    """Create an arq Redis pool for enqueuing from FastAPI request handlers.

    Stored on ``app.state.arq`` in the FastAPI lifespan (web/scheduler roles).
    """
    return await create_pool(_redis_settings())


def _should_dead_letter(ctx: dict) -> bool:
    """True when this is the final permitted attempt (arq will not retry again)."""
    return int(ctx.get("job_try", 1)) >= int(ctx.get("max_tries", MAX_TRIES) or MAX_TRIES)


async def record_dead_letter(
    kind: str,
    ref_id: str | None,
    payload: dict,
    error: str,
    attempts: int = 0,
) -> None:
    """Insert a ``dead_letter`` row for an exhausted retry (inbound or outbound)."""
    try:
        db = get_db()
        db.table("dead_letter").insert(
            {
                "kind": kind,
                "ref_id": ref_id,
                "payload": payload,
                "error": error[:2000] if error else error,
                "attempts": attempts,
            }
        ).execute()
        logger.error("dead_letter recorded kind=%s ref=%s error=%s", kind, ref_id, error)
    except Exception as e:  # never let dead-letter recording mask the original error
        logger.error("Failed to record dead_letter (kind=%s ref=%s): %s", kind, ref_id, e)


# ---------------------------------------------------------------------------
# webhook_events helpers
# ---------------------------------------------------------------------------

def _load_event(db, event_id: str) -> dict | None:
    resp = db.table("webhook_events").select("*").eq("id", event_id).maybe_single().execute()
    return resp.data if resp and resp.data else None


def _mark_event(db, event_id: str, status: str, *, error: str | None = None) -> None:
    update: dict[str, Any] = {"status": status}
    if error is not None:
        update["last_error"] = error[:2000]
    if status in ("done", "failed"):
        update["processed_at"] = datetime.now(timezone.utc).isoformat()
    db.table("webhook_events").update(update).eq("id", event_id).execute()


async def _process_inbound(ctx: dict, event_id: str, kind: str, dispatch) -> dict:
    """Shared inbound-webhook task body: load row, mark processing, dispatch, mark done.

    ``dispatch`` is an async callable taking the loaded event row.
    On failure marks the row ``failed`` and, on the final try, dead-letters, then
    re-raises so arq retries (until exhausted).
    """
    db = get_db()
    event = _load_event(db, event_id)
    if not event:
        logger.warning("%s task: webhook_events row %s not found — skipping", kind, event_id)
        return {"status": "missing", "event_id": event_id}
    if event["status"] == "done":
        return {"status": "already_done", "event_id": event_id}

    # bump attempts + mark processing
    attempts = int(event.get("attempts", 0)) + 1
    db.table("webhook_events").update({"status": "processing", "attempts": attempts}).eq(
        "id", event_id
    ).execute()

    try:
        await dispatch(event)
    except Exception as e:
        _mark_event(db, event_id, "failed", error=str(e))
        if _should_dead_letter(ctx):
            await record_dead_letter(kind, event_id, event.get("payload", {}), str(e), attempts)
        raise

    _mark_event(db, event_id, "done")
    return {"status": "done", "event_id": event_id}


# ---------------------------------------------------------------------------
# Inbound processing tasks
# ---------------------------------------------------------------------------

async def process_stripe_event(ctx: dict, event_id: str) -> dict:
    """Dispatch a persisted Stripe event to the existing webhook handlers."""
    from routers import webhooks

    async def dispatch(event: dict) -> None:
        payload = event.get("payload", {})
        event_type = payload.get("type") or event.get("event_type")
        data = (payload.get("data") or {}).get("object", {})
        if event_type == "customer.subscription.trial_will_end":
            await webhooks.handle_trial_will_end(data)
        elif event_type == "customer.subscription.updated":
            if data.get("status") == "active":
                await webhooks.activate_client_by_subscription(data["id"])
        elif event_type == "customer.subscription.deleted":
            await webhooks.expire_client_by_subscription(data["id"])
        elif event_type == "invoice.payment_failed":
            await webhooks.pause_client_jobs_by_subscription(data.get("subscription"))
        else:
            logger.info("process_stripe_event: unhandled type %s", event_type)

    return await _process_inbound(ctx, event_id, "stripe", dispatch)


async def process_gbp_review(ctx: dict, event_id: str) -> dict:
    """Draft a reply for a GBP review whose resource was fetched at ingest time."""
    from routers import webhooks

    async def dispatch(event: dict) -> None:
        await webhooks.process_review(event.get("payload", {}))

    return await _process_inbound(ctx, event_id, "gbp", dispatch)


async def process_menu_update(ctx: dict, event_id: str) -> dict:
    """Sync a menu item change to the client's configured platforms."""
    from jobs.menu_sync import sync_menu_item

    async def dispatch(event: dict) -> None:
        payload = event.get("payload", {})
        client_id = payload.get("client_id")
        item = payload.get("item", {})
        await sync_menu_item(client_id, item)

    return await _process_inbound(ctx, event_id, "menu", dispatch)


# ---------------------------------------------------------------------------
# Durable outbound wrapper tasks (all five integrations)
# Call sites are migrated to enqueue in their owning phases.
# ---------------------------------------------------------------------------

async def _run_outbound(ctx: dict, kind: str, ref_id: str | None, payload: dict, coro) -> Any:
    """Run an outbound send; on exception (or soft-fail) retry, dead-letter when exhausted."""
    attempts = int(ctx.get("job_try", 1))
    try:
        result = await coro()
    except Exception as e:
        if _should_dead_letter(ctx):
            await record_dead_letter(kind, ref_id, payload, str(e), attempts)
        raise

    # Soft-fail detection for services that swallow errors and return a status.
    soft_fail = None
    if result is False:
        soft_fail = "returned False"
    elif isinstance(result, dict):
        if result.get("sent") is False:
            soft_fail = str(result.get("reason", "send failed"))
        elif result.get("synced") is False:
            soft_fail = str(result.get("message", "sync failed"))

    if soft_fail is not None:
        if _should_dead_letter(ctx):
            await record_dead_letter(kind, ref_id, payload, soft_fail, attempts)
        raise RuntimeError(f"{kind} outbound failed: {soft_fail}")

    return result


async def send_sms_task(ctx: dict, to: str, body: str, state: str = "NSW") -> Any:
    """Durable Twilio SMS send (migrated in Phase 2: jobs/appointment_followup.py)."""
    from services.twilio_sms import send_sms

    return await _run_outbound(
        ctx, "twilio", to, {"to": to, "body": body, "state": state},
        lambda: send_sms(to, body, state),
    )


async def send_email_task(ctx: dict, kind: str, to: str, *args: Any) -> Any:
    """Durable Resend email send (migrated in Phase 1/4).

    ``kind`` selects the sender in ``services.resend_email`` (e.g. 'welcome',
    'trial_day12'); ``args`` are forwarded positionally to that sender.
    """
    from services import resend_email

    fn_name = f"send_{kind}_email"
    fn = getattr(resend_email, fn_name, None)
    if fn is None:
        raise ValueError(f"unknown email kind: {kind}")

    return await _run_outbound(
        ctx, "resend", to, {"kind": kind, "to": to, "args": list(args)},
        lambda: fn(to, *args),
    )


async def post_gbp_reply_task(
    ctx: dict, location_id: str, review_id: str, reply: str, access_token: str
) -> Any:
    """Durable GBP review-reply post (migrated in Phase 4: routers/approve.py)."""
    from services.gbp import post_review_reply

    return await _run_outbound(
        ctx, "gbp_out", review_id,
        {"location_id": location_id, "review_id": review_id, "reply": reply},
        lambda: post_review_reply(location_id, review_id, reply, access_token),
    )


async def square_sync_task(ctx: dict, client: dict, item: dict) -> Any:
    """Durable Square catalog upsert (migrated in Phase 3: jobs/menu_sync.py)."""
    from jobs.menu_sync import _sync_square

    return await _run_outbound(
        ctx, "square", client.get("id"), {"client_id": client.get("id"), "item": item},
        lambda: _sync_square(client, item),
    )


async def dataforseo_task(ctx: dict, keyword: str, location: str, client_suburb: str = "") -> Any:
    """Durable DataForSEO query (migrated in Phase 4: jobs/seo_report.py, competitor_watch.py)."""
    from services.dataforseo import get_local_rankings

    return await _run_outbound(
        ctx, "dataforseo", keyword,
        {"keyword": keyword, "location": location, "client_suburb": client_suburb},
        lambda: get_local_rankings(keyword, location, client_suburb),
    )


# ---------------------------------------------------------------------------
# Cron entrypoint tasks (enqueued by the scheduler container; see scheduler.py)
# ---------------------------------------------------------------------------

async def run_yelp_poll(ctx: dict) -> None:
    from jobs.review_poll import poll_yelp_reviews_all_clients

    await poll_yelp_reviews_all_clients()


async def run_seo_weekly(ctx: dict) -> None:
    from jobs.seo_report import run_seo_rankings_all_clients

    await run_seo_rankings_all_clients()


async def run_competitor_weekly(ctx: dict) -> None:
    from jobs.competitor_watch import run_competitor_snapshots_all_clients

    await run_competitor_snapshots_all_clients()


async def run_appointment_daily(ctx: dict) -> None:
    from jobs.appointment_followup import run_appointment_followup_all_clients

    await run_appointment_followup_all_clients()


async def run_trial_hourly(ctx: dict) -> None:
    from middleware.trial_gate import check_trial_expiries

    await check_trial_expiries()


async def run_trial_emails_daily(ctx: dict) -> None:
    from jobs.trial_emails import run_trial_emails

    await run_trial_emails()


async def reconcile_webhooks(ctx: dict) -> dict:
    """Re-enqueue webhook_events rows stuck 'pending' (mandatory backstop, C4)."""
    from utils.reconcile import reconcile_pending_webhooks

    return await reconcile_pending_webhooks(ctx.get("redis"))


# ---------------------------------------------------------------------------
# arq WorkerSettings
# ---------------------------------------------------------------------------

async def _on_startup(ctx: dict) -> None:
    from db import init_db

    await init_db()
    logger.info("arq worker started (role=worker)")


async def _on_shutdown(ctx: dict) -> None:
    logger.info("arq worker shutting down")


FUNCTIONS = [
    # inbound processing
    process_stripe_event,
    process_gbp_review,
    process_menu_update,
    # durable outbound
    send_sms_task,
    send_email_task,
    post_gbp_reply_task,
    square_sync_task,
    dataforseo_task,
    # cron entrypoints
    run_yelp_poll,
    run_seo_weekly,
    run_competitor_weekly,
    run_appointment_daily,
    run_trial_hourly,
    run_trial_emails_daily,
    reconcile_webhooks,
]


class WorkerSettings:
    """arq worker configuration — ``uv run arq worker.WorkerSettings``."""

    redis_settings = _redis_settings()
    functions = FUNCTIONS
    cron_jobs = [
        # Mandatory reconciliation every 5 minutes (C4).
        cron(reconcile_webhooks, minute=set(range(0, 60, 5)), run_at_startup=False),
    ]
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    max_tries = MAX_TRIES
    job_timeout = JOB_TIMEOUT
    keep_result = KEEP_RESULT
