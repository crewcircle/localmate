"""Tests for the enqueue-only scheduler refactor (Phase 0)."""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


def test_create_scheduler_registers_expected_job_ids():
    import scheduler

    s = scheduler.create_scheduler()
    job_ids = {j.id for j in s.get_jobs()}
    # Original six cron jobs keep their ids + the new reconcile job.
    for expected in [
        "yelp_poll", "seo_weekly", "competitor_weekly",
        "appointment_daily", "trial_hourly", "trial_emails_daily",
        "reconcile_pending",
    ]:
        assert expected in job_ids


def test_cron_job_map_targets_arq_tasks():
    import scheduler

    mapping = {job_id: task for job_id, task, _ in scheduler.CRON_JOBS}
    assert mapping["yelp_poll"] == "run_yelp_poll"
    assert mapping["seo_weekly"] == "run_seo_weekly"
    assert mapping["competitor_weekly"] == "run_competitor_weekly"
    assert mapping["appointment_daily"] == "run_appointment_daily"
    assert mapping["trial_hourly"] == "run_trial_hourly"
    assert mapping["trial_emails_daily"] == "run_trial_emails_daily"
    assert mapping["reconcile_pending"] == "reconcile_webhooks"


@pytest.mark.asyncio
async def test_scheduler_action_enqueues_not_runs_business_logic():
    """The registered action pushes an arq job — it must not run business logic."""
    import scheduler

    pool = MagicMock()
    pool.enqueue_job = AsyncMock()
    pool.close = AsyncMock()

    action = scheduler._make_enqueue("run_seo_weekly")
    with patch("task_queue.get_arq_pool", new_callable=AsyncMock, return_value=pool):
        await action()

    pool.enqueue_job.assert_awaited_once_with("run_seo_weekly")


def test_cron_task_wrappers_exist_for_each_job():
    """Each scheduled arq task name must resolve to a function in task_queue."""
    import task_queue
    import scheduler

    for _job_id, task_name, _trigger in scheduler.CRON_JOBS:
        assert hasattr(task_queue, task_name), f"task_queue missing {task_name}"
