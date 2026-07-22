"""Tests for arq inbound processing task wrappers (Phase 0)."""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from arq import Retry


def _event_db(event_data, claim_ok=True):
    """Mock supabase client.

    ``event_data`` is returned by the load select; the atomic claim
    (update().eq().eq().execute()) returns a row when ``claim_ok`` so the worker
    wins the claim race.
    """
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=event_data
    )
    claim_result = MagicMock(data=[{"id": (event_data or {}).get("id", "x")}] if claim_ok else [])
    db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = claim_result
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
        result = await task_queue.process_stripe_event({"job_try": 1}, "evt-1")

    assert result["status"] == "done"
    mock_activate.assert_awaited_once_with("sub_1")
    # claim flipped to processing
    claim_calls = [c[0][0] for c in db.table.return_value.update.call_args_list]
    assert any(u.get("status") == "processing" for u in claim_calls)
    assert any(u.get("status") == "done" for u in claim_calls)


@pytest.mark.asyncio
async def test_process_gbp_review_calls_process_review():
    import task_queue

    event = {"id": "evt-g", "status": "pending", "attempts": 0, "payload": {"name": "accounts/1/locations/2/reviews/3"}}
    db = _event_db(event)

    with patch("task_queue.get_db", return_value=db), \
         patch("routers.webhooks.process_review", new_callable=AsyncMock) as mock_pr:
        result = await task_queue.process_gbp_review({"job_try": 1}, "evt-g")

    assert result["status"] == "done"
    mock_pr.assert_awaited_once_with({"name": "accounts/1/locations/2/reviews/3"})


@pytest.mark.asyncio
async def test_process_menu_update_calls_sync_menu_item():
    import task_queue

    event = {"id": "evt-m", "status": "pending", "attempts": 0, "payload": {"client_id": "c1", "item": {"name": "Latte"}}}
    db = _event_db(event)

    with patch("task_queue.get_db", return_value=db), \
         patch("jobs.menu_sync.sync_menu_item", new_callable=AsyncMock,
               return_value={"status": "completed", "targets": {"square": {"synced": True}}}) as mock_sync:
        result = await task_queue.process_menu_update({"job_try": 1}, "evt-m")

    assert result["status"] == "done"
    mock_sync.assert_awaited_once_with("c1", {"name": "Latte"})


@pytest.mark.asyncio
async def test_process_menu_update_raises_when_target_failed():
    """A menu target that did not sync must propagate so the task retries."""
    import task_queue

    event = {"id": "evt-mf", "status": "pending", "attempts": 0, "payload": {"client_id": "c1", "item": {"name": "Latte"}}}
    db = _event_db(event)

    with patch("task_queue.get_db", return_value=db), \
         patch("jobs.menu_sync.sync_menu_item", new_callable=AsyncMock,
               return_value={"status": "completed", "targets": {"square": {"synced": False, "message": "boom"}}}):
        with pytest.raises(Retry):
            await task_queue.process_menu_update({"job_try": 1}, "evt-mf")


@pytest.mark.asyncio
async def test_task_raises_retry_on_non_final_failure():
    """A non-final failure must raise arq.Retry (not a plain re-raise) so arq retries,
    and must NOT dead-letter. The row is reset to pending for the next attempt."""
    import task_queue

    event = {"id": "evt-f", "status": "pending", "attempts": 0, "payload": {"type": "customer.subscription.updated", "data": {"object": {"id": "s", "status": "active"}}}}
    db = _event_db(event)

    with patch("task_queue.get_db", return_value=db), \
         patch("routers.webhooks.activate_client_by_subscription", new_callable=AsyncMock, side_effect=RuntimeError("boom")), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(Retry):
            await task_queue.process_stripe_event({"job_try": 1}, "evt-f")
        mock_dl.assert_not_awaited()
    # reset to pending so retry can re-claim
    update_calls = [c[0][0] for c in db.table.return_value.update.call_args_list]
    assert any(u.get("status") == "pending" for u in update_calls)


@pytest.mark.asyncio
async def test_task_dead_letters_and_fails_on_final_try():
    """On the final attempt, mark failed + dead-letter + fail permanently (no Retry)."""
    import task_queue

    event = {"id": "evt-x", "status": "pending", "attempts": 4, "payload": {"type": "customer.subscription.updated", "data": {"object": {"id": "s", "status": "active"}}}}
    db = _event_db(event)

    with patch("task_queue.get_db", return_value=db), \
         patch("routers.webhooks.activate_client_by_subscription", new_callable=AsyncMock, side_effect=RuntimeError("boom")), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(RuntimeError):
            await task_queue.process_stripe_event({"job_try": task_queue.MAX_TRIES}, "evt-x")
        mock_dl.assert_awaited_once()
    update_calls = [c[0][0] for c in db.table.return_value.update.call_args_list]
    assert any(u.get("status") == "failed" for u in update_calls)


@pytest.mark.asyncio
async def test_lost_claim_race_is_skipped():
    """If another worker already claimed the row, this worker must not dispatch."""
    import task_queue

    event = {"id": "evt-c", "status": "pending", "attempts": 0, "payload": {"type": "x"}}
    db = _event_db(event, claim_ok=False)

    with patch("task_queue.get_db", return_value=db), \
         patch("routers.webhooks.activate_client_by_subscription", new_callable=AsyncMock) as mock_activate:
        result = await task_queue.process_stripe_event({"job_try": 1}, "evt-c")

    assert result["status"] == "already_claimed"
    mock_activate.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_event_row_skips():
    import task_queue

    db = _event_db(None)
    with patch("task_queue.get_db", return_value=db):
        result = await task_queue.process_stripe_event({"job_try": 1}, "nope")
    assert result["status"] == "missing"


@pytest.mark.asyncio
async def test_already_done_event_is_noop():
    import task_queue

    db = _event_db({"id": "e", "status": "done", "attempts": 1, "payload": {}})
    with patch("task_queue.get_db", return_value=db):
        result = await task_queue.process_stripe_event({"job_try": 1}, "e")
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
