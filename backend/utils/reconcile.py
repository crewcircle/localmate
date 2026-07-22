"""Webhook reconciliation (Phase 0 — mandatory, C4).

Re-enqueues ``webhook_events`` rows stuck in ``pending`` older than a threshold.
This is the durability backstop for the edge case where Redis was briefly
unavailable when the request handler tried to enqueue: the row was still
persisted as ``pending``, and this job picks it up.

Registered every 5 minutes (arq cron in ``queue.WorkerSettings.cron_jobs`` and,
in the scheduler role, an APScheduler enqueue of ``reconcile_webhooks``).
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


async def reconcile_pending_webhooks(redis=None) -> dict:
    """Find stale ``pending`` webhook_events and re-enqueue their processing task.

    ``redis`` is an arq pool (``ctx['redis']`` when called from the worker cron).
    When ``None`` (e.g. called from APScheduler), a fresh pool is created.
    """
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)).isoformat()

    resp = (
        db.table("webhook_events")
        .select("id, provider")
        .eq("status", "pending")
        .lt("created_at", cutoff)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return {"reenqueued": 0}

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
                await redis.enqueue_job(task, row["id"])
                reenqueued += 1
            except Exception as e:
                logger.error("reconcile: failed to re-enqueue %s: %s", row["id"], e)
    finally:
        if own_pool:
            try:
                await redis.close()
            except Exception:
                pass

    logger.info("reconcile_pending_webhooks re-enqueued %d rows", reenqueued)
    return {"reenqueued": reenqueued}
