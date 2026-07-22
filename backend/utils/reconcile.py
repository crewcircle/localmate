"""Webhook reconciliation (Phase 0 — mandatory, C4).

Re-enqueues ``webhook_events`` rows stuck in ``pending`` older than a threshold,
and recovers rows stranded in ``processing`` by a worker that crashed mid-job.
This is the durability backstop for two edge cases:
  * Redis was briefly unavailable when the request handler tried to enqueue — the
    row was persisted ``pending`` but no job exists; we re-enqueue it.
  * A worker claimed a row (``processing``) and then died before finishing — the
    lease (``processing_started_at``) is stale, so we reset it to ``pending`` and
    re-enqueue. Staleness of a ``processing`` row is judged by the lease start,
    NOT ``created_at``, so a row that sat queued a long time before processing
    began is never reclaimed while it is actively running.

Registered as a SINGLE arq cron every 5 minutes in
``task_queue.WorkerSettings.cron_jobs`` (it is intentionally NOT also scheduled in
``scheduler.py`` — one trigger only, to avoid duplicate re-enqueues).

Idempotency: re-enqueues use a deterministic arq ``_job_id`` derived from the
event id, so a job already queued/running for that event is NOT duplicated (arq
drops an enqueue with a ``_job_id`` that already exists). Combined with the atomic
``pending`` claim in ``task_queue._process_inbound``, this keeps processing
effectively once-per-event even when the initial enqueue and a reconcile pass
race.
"""
import logging
from datetime import datetime, timedelta, timezone

from db import get_db

logger = logging.getLogger(__name__)

# Rows older than this still 'pending' are considered orphaned and re-enqueued.
STALE_MINUTES = 5

# provider -> processing task name
_PROVIDER_TASK = {
    "stripe": "process_stripe_event",
    "gbp": "process_gbp_review",
    "menu": "process_menu_update",
}


def _job_id(event_id: str) -> str:
    """Deterministic arq job id for an event's processing job.

    Using a stable id makes re-enqueue idempotent: arq will not queue a second
    job while one with the same id is queued/in-flight.
    """
    return f"process-webhook-{event_id}"


def _recover_stale_processing(db, cutoff: str) -> int:
    """Reset rows whose ``processing`` lease is older than the cutoff to ``pending``.

    Staleness is judged by ``processing_started_at`` (the lease start recorded on
    the atomic pending→processing claim), NOT ``created_at``. Basing it on
    ``created_at`` would let an event that sat queued > STALE_MINUTES and then
    began processing be reset to ``pending`` while it is actively running,
    causing duplicate processing. These stale leases are held by a worker that
    crashed mid-job; resetting them (and clearing the lease) lets the pending
    sweep below re-enqueue them. Returns the number reset.
    """
    resp = (
        db.table("webhook_events")
        .update({"status": "pending", "processing_started_at": None})
        .eq("status", "processing")
        .lt("processing_started_at", cutoff)
        .execute()
    )
    recovered = len(resp.data) if resp and resp.data else 0
    if recovered:
        logger.warning("reconcile: recovered %d stale 'processing' rows", recovered)
    return recovered


async def reconcile_pending_webhooks(redis=None) -> dict:
    """Recover stale ``processing`` leases and re-enqueue stale ``pending`` rows.

    ``redis`` is an arq pool (``ctx['redis']`` when called from the worker cron).
    When ``None`` (e.g. called directly), a fresh pool is created.
    """
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)).isoformat()

    # 1) Recover leases held by crashed workers (processing → pending).
    recovered = _recover_stale_processing(db, cutoff)

    # 2) Re-enqueue stale pending rows (including the ones just recovered).
    resp = (
        db.table("webhook_events")
        .select("id, provider")
        .eq("status", "pending")
        .lt("created_at", cutoff)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return {"reenqueued": 0, "recovered": recovered}

    own_pool = False
    if redis is None:
        from task_queue import get_arq_pool

        redis = await get_arq_pool()
        own_pool = True

    reenqueued = 0
    try:
        for row in rows:
            task = _PROVIDER_TASK.get(row.get("provider"))
            if not task:
                logger.warning("reconcile: unknown provider %s for %s", row.get("provider"), row["id"])
                continue
            try:
                # Deterministic _job_id → arq ignores a duplicate enqueue for an
                # event whose job is already queued/running.
                job = await redis.enqueue_job(task, row["id"], _job_id=_job_id(row["id"]))
                if job is not None:
                    reenqueued += 1
            except Exception as e:
                logger.error("reconcile: failed to re-enqueue %s: %s", row["id"], e)
    finally:
        if own_pool:
            try:
                await redis.close()
            except Exception:
                pass

    logger.info(
        "reconcile_pending_webhooks recovered %d, re-enqueued %d rows", recovered, reenqueued
    )
    return {"reenqueued": reenqueued, "recovered": recovered}
