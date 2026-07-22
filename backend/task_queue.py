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

from arq import cron, create_pool, Retry
from arq.connections import RedisSettings

from config import settings
from db import get_db

logger = logging.getLogger(__name__)

# Retry / timeout policy (shared by WorkerSettings and the dead-letter check).
MAX_TRIES = 5
JOB_TIMEOUT = 120  # seconds
KEEP_RESULT = 3600  # seconds

# Backoff (seconds) applied before retries 2, 3, 4, 5 respectively. arq only
# retries a task when it raises ``arq.Retry`` (a plain exception is marked failed
# immediately), so every retryable failure below is turned into ``Retry(defer=…)``.
RETRY_BACKOFF = [10, 30, 60, 120]


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def get_arq_pool():
    """Create an arq Redis pool for enqueuing from FastAPI request handlers.

    Stored on ``app.state.arq`` in the FastAPI lifespan (web/scheduler roles).
    """
    return await create_pool(_redis_settings())


def _should_dead_letter(ctx: dict) -> bool:
    """True when this is the final permitted attempt (arq will not retry again).

    ``max_tries`` is NOT present in the arq job ctx (ctx carries ``job_try``,
    ``job_id``, ``enqueue_time``, ``score`` plus the worker ctx), so the cap is
    read from the :data:`MAX_TRIES` constant that also configures
    ``WorkerSettings.max_tries``.
    """
    return int(ctx.get("job_try", 1)) >= MAX_TRIES


def _retry_defer(job_try: int) -> int:
    """Seconds to defer the next retry for the given (1-based) attempt number."""
    idx = min(max(job_try - 1, 0), len(RETRY_BACKOFF) - 1)
    return RETRY_BACKOFF[idx]


def _detect_soft_fail(result: Any) -> str | None:
    """Return a failure reason when an outbound call soft-failed, else ``None``.

    Several services swallow errors and return a status dict instead of raising.
    A ``skipped`` result (e.g. Twilio skipping on an AU public holiday) is a
    legitimate no-op, NOT a failure, and must not be retried or dead-lettered.
    """
    if result is False:
        return "returned False"
    if isinstance(result, dict):
        if result.get("skipped"):
            return None
        if result.get("sent") is False:
            return str(result.get("reason", "send failed"))
        if result.get("synced") is False:
            return str(result.get("message", "sync failed"))
    return None


def _load_client(db, client_id: str) -> dict | None:
    """Load a client row by id (used to resolve+decrypt credentials in-worker)."""
    resp = db.table("clients").select("*").eq("id", client_id).maybe_single().execute()
    return resp.data if resp and resp.data else None


async def _resolve_gbp_access_token(client: dict) -> str:
    """Decrypt the client's stored GBP access token, refreshing when absent.

    Both tokens are stored Fernet-encrypted (see ``routers/auth.gbp_callback``);
    decryption happens only in-worker so no plaintext token is ever enqueued.
    """
    from services.crypto import decrypt
    from services.gbp import refresh_access_token

    enc_access = client.get("gbp_access_token", "")
    enc_refresh = client.get("gbp_refresh_token", "")
    access_token = decrypt(enc_access) if enc_access else ""
    if not access_token and enc_refresh:
        access_token = await refresh_access_token(decrypt(enc_refresh))
    return access_token


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
    if status == "pending":
        # Releasing the lease (retry reset) — clear the lease start so the next
        # claim records a fresh one and reconcile's stale check is accurate.
        update["processing_started_at"] = None
    db.table("webhook_events").update(update).eq("id", event_id).execute()


async def _process_inbound(ctx: dict, event_id: str, kind: str, dispatch) -> dict:
    """Shared inbound-webhook task body: atomically claim the row, dispatch, mark done.

    ``dispatch`` is an async callable taking the loaded event row.

    Concurrency: the claim is an atomic UPDATE gated on ``status = 'pending'`` (or
    a stale ``processing`` lease) so that duplicate enqueues — the initial enqueue
    plus a reconcile re-enqueue, or two reconcile passes — cannot both execute the
    business logic. A worker that loses the claim race returns ``already_claimed``.

    Failure handling: arq only retries on ``arq.Retry`` (a plain re-raise is marked
    failed immediately and never retried), so a non-final failure raises
    ``Retry(defer=<backoff>)`` after resetting the row to ``pending`` for the next
    attempt. On the final attempt the row is marked ``failed``, a ``dead_letter``
    row is written, and the task fails permanently.
    """
    db = get_db()
    event = _load_event(db, event_id)
    if not event:
        logger.warning("%s task: webhook_events row %s not found — skipping", kind, event_id)
        return {"status": "missing", "event_id": event_id}
    if event["status"] == "done":
        return {"status": "already_done", "event_id": event_id}

    # Atomically claim the row: flip pending → processing only if still pending.
    # ``processing_started_at`` records the lease start so reconcile bases stale
    # recovery on when processing began (NOT ``created_at``) — a row that sat
    # queued a long time then started processing must not be reclaimed while it
    # is actively running.
    # Reconcile handles rows stuck in `processing` (crashed worker) by resetting
    # them to `pending`, so here we only accept `pending`.
    attempts = int(event.get("attempts", 0)) + 1
    claim = (
        db.table("webhook_events")
        .update({
            "status": "processing",
            "attempts": attempts,
            "processing_started_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", event_id)
        .eq("status", "pending")
        .execute()
    )
    if not (claim and claim.data):
        # Another worker already claimed/processed this row.
        logger.info("%s task: event %s already claimed — skipping", kind, event_id)
        return {"status": "already_claimed", "event_id": event_id}

    try:
        await dispatch(event)
    except Exception as e:
        if _should_dead_letter(ctx):
            _mark_event(db, event_id, "failed", error=str(e))
            await record_dead_letter(kind, event_id, event.get("payload", {}), str(e), attempts)
            raise
        # Non-final attempt: reset to pending so the retry can re-claim, then ask
        # arq to retry (a plain re-raise would NOT be retried).
        _mark_event(db, event_id, "pending", error=str(e))
        raise Retry(defer=_retry_defer(int(ctx.get("job_try", 1))))

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
        location_id = payload.get("location_id")
        item = payload.get("item", {})
        origin = payload.get("origin", "sheets")
        result = await sync_menu_item(client_id, location_id, item, origin)
        # sync_menu_item swallows per-target errors and returns a status dict.
        # A hard failure (client missing) or any un-synced target must propagate
        # so the inbound task retries / dead-letters rather than marking done.
        if result.get("status") == "failed":
            raise RuntimeError(f"menu sync failed: {result.get('error')}")
        failed = {
            target: r.get("message", "sync failed")
            for target, r in (result.get("targets") or {}).items()
            if not r.get("synced")
        }
        if failed:
            raise RuntimeError(f"menu sync targets failed: {failed}")

    return await _process_inbound(ctx, event_id, "menu", dispatch)


# ---------------------------------------------------------------------------
# Durable outbound wrapper tasks (all five integrations)
# Call sites are migrated to enqueue in their owning phases.
# ---------------------------------------------------------------------------

async def _run_outbound(ctx: dict, kind: str, ref_id: str | None, payload: dict, coro) -> Any:
    """Run an outbound send; on failure retry via ``arq.Retry``, dead-letter when exhausted.

    Handles both hard failures (the coroutine raises) and soft failures (a service
    that swallows the error and returns a status dict / ``False``). A ``skipped``
    result is a legitimate no-op and is returned as success. arq only retries on
    ``arq.Retry``, so non-final failures raise that; the final attempt records a
    ``dead_letter`` row and fails permanently.
    """
    job_try = int(ctx.get("job_try", 1))
    try:
        result = await coro()
    except Exception as e:
        if _should_dead_letter(ctx):
            await record_dead_letter(kind, ref_id, payload, str(e), job_try)
            raise
        logger.warning("%s outbound try %d failed: %s — retrying", kind, job_try, e)
        raise Retry(defer=_retry_defer(job_try))

    soft_fail = _detect_soft_fail(result)
    if soft_fail is not None:
        if _should_dead_letter(ctx):
            await record_dead_letter(kind, ref_id, payload, soft_fail, job_try)
            raise RuntimeError(f"{kind} outbound failed: {soft_fail}")
        logger.warning("%s outbound try %d soft-failed: %s — retrying", kind, job_try, soft_fail)
        raise Retry(defer=_retry_defer(job_try))

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

    ``kind`` selects the template in ``services.resend_email`` (e.g. 'welcome',
    'trial_day12'); ``args`` are forwarded positionally (first is business_name).

    Uses the *strict* sender so a Resend transport/provider failure RAISES (the
    plain ``send_*_email`` helpers swallow errors and return ``None`` for both
    success and failure, which the durable path cannot distinguish).
    """
    from services.resend_email import send_email_strict

    return await _run_outbound(
        ctx, "resend", to, {"kind": kind, "to": to, "args": list(args)},
        lambda: send_email_strict(kind, to, *args),
    )


async def post_gbp_reply_task(
    ctx: dict, client_id: str, location_id: str, review_id: str, reply: str
) -> Any:
    """Durable GBP review-reply post (migrated in Phase 4: routers/approve.py).

    Security (C4/D4): only stable IDs are enqueued — never the OAuth token. The
    GBP access token is loaded and Fernet-decrypted **inside the worker**, and
    refreshed on demand, so no credential is ever serialized into Redis/AOF or
    logged in arq's task-args line.
    """
    from services.gbp import post_review_reply

    async def _coro() -> Any:
        # Load client, resolve+decrypt the token, and post — ALL inside the
        # coroutine so every failure path (DB outage, missing client, decrypt
        # error, token-refresh failure, transport error) is caught by
        # ``_run_outbound`` and gets the retry + dead-letter treatment (C4).
        db = get_db()
        client = _load_client(db, client_id)
        if not client:
            raise RuntimeError(f"post_gbp_reply_task: client {client_id} not found")
        access_token = await _resolve_gbp_access_token(client)
        return await post_review_reply(location_id, review_id, reply, access_token)

    return await _run_outbound(
        ctx, "gbp_out", review_id,
        {"client_id": client_id, "location_id": location_id, "review_id": review_id, "reply": reply},
        _coro,
    )


async def square_sync_task(ctx: dict, client_id: str, location_id: str, item: dict) -> Any:
    """Durable Square catalog upsert (Phase 3: per-client OAuth token).

    Security (C4/D4): enqueues only ``client_id`` + ``location_id`` + the item —
    never the client record (which carries square_access_token / PMS credentials).
    The client row and Square token are resolved inside the worker via
    ``square_oauth.get_valid_token`` (per-client OAuth, not global settings).
    """
    from services.square_oauth import get_valid_token
    from services.square_catalog import upsert_item as square_upsert

    async def _coro() -> Any:
        db = get_db()
        client = _load_client(db, client_id)
        if not client:
            raise RuntimeError(f"square_sync_task: client {client_id} not found")
        loc_resp = (
            db.table("locations")
            .select("*")
            .eq("id", location_id)
            .maybe_single()
            .execute()
        )
        if not loc_resp.data:
            raise RuntimeError(f"square_sync_task: location {location_id} not found")
        access_token = await get_valid_token(client)
        result = await square_upsert(
            access_token, loc_resp.data["square_location_id"], item
        )
        return {"synced": True, "external_id": result.get("id"),
                "external_version": result.get("version")}

    return await _run_outbound(
        ctx, "square", client_id,
        {"client_id": client_id, "location_id": location_id, "item": item},
        _coro,
    )


async def dataforseo_task(ctx: dict, keyword: str, location: str, client_suburb: str = "") -> Any:
    """Durable DataForSEO query (migrated in Phase 4: jobs/seo_report.py, competitor_watch.py).

    Uses the *strict* query so a transport/API failure RAISES and is retried /
    dead-lettered — the non-strict ``get_local_rankings`` swallows API errors and
    returns ``position: None``, which the durable path cannot distinguish from a
    genuine "not ranked". A real "not found in top 30" still returns normally.
    """
    from services.dataforseo import get_local_rankings_strict

    return await _run_outbound(
        ctx, "dataforseo", keyword,
        {"keyword": keyword, "location": location, "client_suburb": client_suburb},
        lambda: get_local_rankings_strict(keyword, location, client_suburb),
    )


async def dataforseo_maps_task(
    ctx: dict, keyword: str, location: str, client_suburb: str = "",
    business_name: str = "", place_id: str = "",
) -> Any:
    """Durable DataForSEO Maps/Local-Pack query (Phase 4: jobs/seo_report.py).

    Uses the *strict* variant so transport/API failures are retried and
    dead-lettered. A genuine "not matched in the local pack" returns
    ``map_position: None`` normally.
    """
    from services.dataforseo import get_maps_rankings_strict

    return await _run_outbound(
        ctx, "dataforseo", keyword,
        {"keyword": keyword, "location": location, "client_suburb": client_suburb,
         "business_name": business_name, "place_id": place_id},
        lambda: get_maps_rankings_strict(
            keyword, location, client_suburb, business_name, place_id
        ),
    )


async def provision_gbp_notifications_task(ctx: dict, client_id: str) -> Any:
    """Durable GBP notification provisioning task (Phase 4, C4).

    Enqueued from ``routers/auth.py::gbp_callback`` after tokens are stored.
    ``provision_gbp_notifications`` returns a status dict (does not raise), so
    this wrapper inspects the status: ``failed`` triggers retry/dead-letter,
    ``active`` (or any other) is returned as success.

    Only ``client_id`` is enqueued — the GCP SA key and GBP access token are
    loaded/decrypted inside the worker, never serialized into Redis.
    """
    from services.gbp_provisioning import provision_gbp_notifications

    job_try = int(ctx.get("job_try", 1))

    try:
        result = await provision_gbp_notifications(client_id)
    except Exception as e:
        if _should_dead_letter(ctx):
            await record_dead_letter("gbp_provisioning", client_id, {"client_id": client_id}, str(e), job_try)
            raise
        logger.warning("GBP provisioning try %d failed: %s — retrying", job_try, e)
        raise Retry(defer=_retry_defer(job_try))

    if isinstance(result, dict) and result.get("status") == "failed":
        error = result.get("error", "provisioning failed")
        if _should_dead_letter(ctx):
            await record_dead_letter("gbp_provisioning", client_id, {"client_id": client_id}, error, job_try)
            raise RuntimeError(f"GBP provisioning failed: {error}")
        logger.warning("GBP provisioning try %d failed: %s — retrying", job_try, error)
        raise Retry(defer=_retry_defer(job_try))

    return result


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

    await run_trial_emails(ctx.get("redis"))


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
    dataforseo_maps_task,
    provision_gbp_notifications_task,
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
