"""Tests for dead-letter recording on exhausted retries (Phase 0)."""
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.asyncio
async def test_record_dead_letter_inserts_row():
    import task_queue

    db = MagicMock()
    with patch("task_queue.get_db", return_value=db):
        await task_queue.record_dead_letter(
            "twilio", "+61400000000", {"body": "hi"}, "network error", attempts=5
        )

    insert_arg = db.table.return_value.insert.call_args[0][0]
    assert insert_arg["kind"] == "twilio"
    assert insert_arg["ref_id"] == "+61400000000"
    assert insert_arg["payload"] == {"body": "hi"}
    assert insert_arg["error"] == "network error"
    assert insert_arg["attempts"] == 5
    db.table.assert_called_with("dead_letter")


@pytest.mark.asyncio
async def test_record_dead_letter_swallows_db_error():
    """Recording a dead-letter must never raise (would mask original error)."""
    import task_queue

    db = MagicMock()
    db.table.return_value.insert.return_value.execute.side_effect = RuntimeError("db down")
    with patch("task_queue.get_db", return_value=db):
        # Should not raise
        await task_queue.record_dead_letter("gbp_out", "r1", {}, "boom")


def test_should_dead_letter_only_on_final_try():
    import task_queue

    assert task_queue._should_dead_letter({"job_try": 5}) is True
    assert task_queue._should_dead_letter({"job_try": 6}) is True
    assert task_queue._should_dead_letter({"job_try": 2}) is False
    # defaults to MAX_TRIES for the cap (max_tries is NOT in the arq ctx)
    assert task_queue._should_dead_letter({"job_try": task_queue.MAX_TRIES}) is True
    assert task_queue._should_dead_letter({"job_try": task_queue.MAX_TRIES - 1}) is False


@pytest.mark.asyncio
async def test_inbound_task_dead_letters_on_final_try():
    """When processing fails on the final try, a dead_letter row is written."""
    import task_queue

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"id": "evt-1", "status": "pending", "attempts": 4, "payload": {"foo": "bar"}}
    )
    # atomic claim succeeds
    db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "evt-1"}]
    )

    async def failing_dispatch(event):
        raise ValueError("handler blew up")

    with patch("task_queue.get_db", return_value=db), \
         patch("task_queue.record_dead_letter") as mock_dl:
        # AsyncMock via patching: record_dead_letter is async
        async def _dl(*a, **k):
            return None
        mock_dl.side_effect = _dl

        ctx = {"job_try": task_queue.MAX_TRIES}
        with pytest.raises(ValueError):
            await task_queue._process_inbound(ctx, "evt-1", "stripe", failing_dispatch)

        mock_dl.assert_called_once()
        args = mock_dl.call_args[0]
        assert args[0] == "stripe"
        assert args[1] == "evt-1"
