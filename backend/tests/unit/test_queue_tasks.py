"""Tests for arq inbound processing task wrappers (Phase 0)."""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


def _event_db(event_data, insert_id="x"):
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=event_data
    )
    return db


@pytest.mark.asyncio
async def test_process_stripe_event_dispatches_and_marks_done():
    import task_queue

    event = {
        "id": "evt-1",
        "status": "pending",
        "attempts": 0,
        "payload": {"type": "customer.subscription.updated", "data": {"object": {"id": "sub_1", "status": "active"}}},
    }
    db = _event_db(event)

    with patch("task_queue.get_db", return_value=db), \
         patch("routers.webhooks.activate_client_by_subscription", new_callable=AsyncMock) as mock_activate:
        result = await task_queue.process_stripe_event({"job_try": 1, "max_tries": 5}, "evt-1")

    assert result["status"] == "done"
    mock_activate.assert_awaited_once_with("sub_1")
    # status flipped to done at the end
    update_calls = [c[0][0] for c in db.table.return_value.update.call_args_list]
    assert any(u.get("status") == "processing" for u in update_calls)
    assert any(u.get("status") == "done" for u in update_calls)


@pytest.mark.asyncio
async def test_process_gbp_review_calls_process_review():
    import task_queue

    event = {"id": "evt-g", "status": "pending", "attempts": 0, "payload": {"name": "accounts/1/locations/2/reviews/3"}}
    db = _event_db(event)

    with patch("task_queue.get_db", return_value=db), \
         patch("routers.webhooks.process_review", new_callable=AsyncMock) as mock_pr:
        result = await task_queue.process_gbp_review({"job_try": 1, "max_tries": 5}, "evt-g")

    assert result["status"] == "done"
    mock_pr.assert_awaited_once_with({"name": "accounts/1/locations/2/reviews/3"})


@pytest.mark.asyncio
async def test_process_menu_update_calls_sync_menu_item():
    import task_queue

    event = {"id": "evt-m", "status": "pending", "attempts": 0, "payload": {"client_id": "c1", "item": {"name": "Latte"}}}
    db = _event_db(event)

    with patch("task_queue.get_db", return_value=db), \
         patch("jobs.menu_sync.sync_menu_item", new_callable=AsyncMock) as mock_sync:
        result = await task_queue.process_menu_update({"job_try": 1, "max_tries": 5}, "evt-m")

    assert result["status"] == "done"
    mock_sync.assert_awaited_once_with("c1", {"name": "Latte"})


@pytest.mark.asyncio
async def test_task_reraises_on_failure_for_retry():
    import task_queue

    event = {"id": "evt-f", "status": "pending", "attempts": 0, "payload": {"type": "customer.subscription.updated", "data": {"object": {"id": "s", "status": "active"}}}}
    db = _event_db(event)

    with patch("task_queue.get_db", return_value=db), \
         patch("routers.webhooks.activate_client_by_subscription", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        # not final try → re-raises, does NOT dead-letter
        with patch("task_queue.record_dead_letter") as mock_dl:
            async def _dl(*a, **k):
                return None
            mock_dl.side_effect = _dl
            with pytest.raises(RuntimeError):
                await task_queue.process_stripe_event({"job_try": 1, "max_tries": 5}, "evt-f")
            mock_dl.assert_not_called()
    # marked failed
    update_calls = [c[0][0] for c in db.table.return_value.update.call_args_list]
    assert any(u.get("status") == "failed" for u in update_calls)


@pytest.mark.asyncio
async def test_missing_event_row_skips():
    import task_queue

    db = _event_db(None)
    with patch("task_queue.get_db", return_value=db):
        result = await task_queue.process_stripe_event({"job_try": 1, "max_tries": 5}, "nope")
    assert result["status"] == "missing"


@pytest.mark.asyncio
async def test_already_done_event_is_noop():
    import task_queue

    db = _event_db({"id": "e", "status": "done", "attempts": 1, "payload": {}})
    with patch("task_queue.get_db", return_value=db):
        result = await task_queue.process_stripe_event({"job_try": 1, "max_tries": 5}, "e")
    assert result["status"] == "already_done"


def test_worker_settings_registers_all_functions():
    import task_queue

    names = {f.__name__ for f in task_queue.WorkerSettings.functions}
    for expected in [
        "process_stripe_event", "process_gbp_review", "process_menu_update",
        "send_sms_task", "send_email_task", "post_gbp_reply_task",
        "square_sync_task", "dataforseo_task",
        "run_yelp_poll", "run_seo_weekly", "run_competitor_weekly",
        "run_appointment_daily", "run_trial_hourly", "run_trial_emails_daily",
        "reconcile_webhooks",
    ]:
        assert expected in names, f"{expected} not registered"


def test_worker_settings_has_reconcile_cron():
    import task_queue

    assert len(task_queue.WorkerSettings.cron_jobs) >= 1
