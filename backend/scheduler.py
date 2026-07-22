"""Enqueue-only scheduler (Phase 0).

Runs ONLY in the dedicated ``scheduler``-role container (single-active — NOT
HA/leader-election; see C4). Each cron trigger enqueues an arq job on the shared
Redis pool rather than executing business logic in-process. The worker container
executes the enqueued jobs. This container must be single-instance so cron jobs
fire exactly once (no duplicate fire); no advisory lock is used (that is D8-B).

NOTE: the mandatory 5-minute webhook reconciliation (C4) is NOT scheduled here —
it is registered as an arq ``cron_job`` in ``task_queue.WorkerSettings`` and runs
on the worker. Scheduling it in both places would double-fire reconciliation and
enqueue duplicate processing jobs, so there is exactly ONE reconcile trigger.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)
AEST = pytz.timezone("Australia/Sydney")

# APScheduler job id -> arq task name. Job ids are unchanged from the pre-queue
# scheduler so existing operational docs/monitoring keep working.
CRON_JOBS = [
    # (job_id, arq_task_name, CronTrigger)
    ("yelp_poll", "run_yelp_poll", CronTrigger(hour=0)),
    ("seo_weekly", "run_seo_weekly", CronTrigger(day_of_week="mon", hour=6)),
    ("competitor_weekly", "run_competitor_weekly", CronTrigger(day_of_week="sun", hour=22)),
    ("appointment_daily", "run_appointment_daily", CronTrigger(hour=8)),
    ("trial_hourly", "run_trial_hourly", CronTrigger(minute=0)),
    ("trial_emails_daily", "run_trial_emails_daily", CronTrigger(hour=9)),
    # Reconciliation is NOT scheduled here — it is an arq cron on the worker
    # (task_queue.WorkerSettings.cron_jobs) so it fires from exactly one place.
]


def _make_enqueue(task_name: str):
    """Return an async APScheduler action that enqueues ``task_name`` on arq."""

    async def _enqueue() -> None:
        from task_queue import get_arq_pool

        pool = await get_arq_pool()
        try:
            await pool.enqueue_job(task_name)
            logger.info("scheduler enqueued arq task %s", task_name)
        finally:
            try:
                await pool.close()
            except Exception:
                pass

    return _enqueue


def create_scheduler() -> AsyncIOScheduler:
    """Build the enqueue-only scheduler. Every job pushes an arq job; the
    scheduler process never runs business logic itself."""
    scheduler = AsyncIOScheduler(timezone=AEST)
    for job_id, task_name, trigger in CRON_JOBS:
        scheduler.add_job(_make_enqueue(task_name), trigger, id=job_id)
    return scheduler
