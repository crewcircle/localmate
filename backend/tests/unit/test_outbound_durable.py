"""Tests for durable outbound wrapper tasks (Phase 0) — all five integrations."""
from unittest.mock import patch, AsyncMock

import pytest


@pytest.mark.asyncio
async def test_send_sms_task_success():
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock, return_value={"sent": True, "sid": "SM1"}):
        result = await task_queue.send_sms_task({"job_try": 1, "max_tries": 5}, "+61400000000", "hi")
    assert result["sent"] is True


@pytest.mark.asyncio
async def test_send_sms_task_soft_fail_reraises_for_retry():
    """{sent: False} is a soft-fail — the task must raise so arq retries."""
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock, return_value={"sent": False, "reason": "boom"}), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        # not final try → raise, no dead-letter
        with pytest.raises(RuntimeError):
            await task_queue.send_sms_task({"job_try": 1, "max_tries": 5}, "+61", "hi")
        mock_dl.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_sms_task_dead_letters_on_final_try():
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock, return_value={"sent": False, "reason": "gone"}), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(RuntimeError):
            await task_queue.send_sms_task({"job_try": 5, "max_tries": 5}, "+61", "hi")
        mock_dl.assert_awaited_once()
        assert mock_dl.call_args[0][0] == "twilio"


@pytest.mark.asyncio
async def test_send_sms_task_exception_dead_letters_on_final_try():
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock, side_effect=ConnectionError("net")), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(ConnectionError):
            await task_queue.send_sms_task({"job_try": 5, "max_tries": 5}, "+61", "hi")
        mock_dl.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_email_task_dispatches_by_kind():
    import task_queue

    with patch("services.resend_email.send_welcome_email", new_callable=AsyncMock, return_value=None) as mock_send:
        await task_queue.send_email_task({"job_try": 1, "max_tries": 5}, "welcome", "a@b.com", "Biz", "c1")
    mock_send.assert_awaited_once_with("a@b.com", "Biz", "c1")


@pytest.mark.asyncio
async def test_send_email_task_unknown_kind_raises():
    import task_queue

    with pytest.raises(ValueError):
        await task_queue.send_email_task({"job_try": 1, "max_tries": 5}, "nonexistent", "a@b.com")


@pytest.mark.asyncio
async def test_post_gbp_reply_task_soft_fail_reraises():
    import task_queue

    with patch("services.gbp.post_review_reply", new_callable=AsyncMock, return_value=False), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock):
        with pytest.raises(RuntimeError):
            await task_queue.post_gbp_reply_task({"job_try": 1, "max_tries": 5}, "loc", "rev", "reply", "tok")


@pytest.mark.asyncio
async def test_post_gbp_reply_task_success():
    import task_queue

    with patch("services.gbp.post_review_reply", new_callable=AsyncMock, return_value=True):
        result = await task_queue.post_gbp_reply_task({"job_try": 1, "max_tries": 5}, "loc", "rev", "reply", "tok")
    assert result is True


@pytest.mark.asyncio
async def test_square_sync_task_soft_fail_reraises():
    import task_queue

    with patch("jobs.menu_sync._sync_square", new_callable=AsyncMock, return_value={"synced": False, "message": "bad"}), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(RuntimeError):
            await task_queue.square_sync_task({"job_try": 5, "max_tries": 5}, {"id": "c1"}, {"name": "Latte"})
        mock_dl.assert_awaited_once()
        assert mock_dl.call_args[0][0] == "square"


@pytest.mark.asyncio
async def test_square_sync_task_success():
    import task_queue

    with patch("jobs.menu_sync._sync_square", new_callable=AsyncMock, return_value={"synced": True, "message": "Synced to Square"}):
        result = await task_queue.square_sync_task({"job_try": 1, "max_tries": 5}, {"id": "c1"}, {"name": "Latte"})
    assert result["synced"] is True


@pytest.mark.asyncio
async def test_dataforseo_task_success():
    import task_queue

    with patch("services.dataforseo.get_local_rankings", new_callable=AsyncMock, return_value={"keyword": "dentist", "position": 3}):
        result = await task_queue.dataforseo_task({"job_try": 1, "max_tries": 5}, "dentist", "Bondi")
    assert result["position"] == 3


@pytest.mark.asyncio
async def test_dataforseo_task_exception_dead_letters_on_final():
    import task_queue

    with patch("services.dataforseo.get_local_rankings", new_callable=AsyncMock, side_effect=TimeoutError("slow")), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(TimeoutError):
            await task_queue.dataforseo_task({"job_try": 5, "max_tries": 5}, "dentist", "Bondi")
        mock_dl.assert_awaited_once()
        assert mock_dl.call_args[0][0] == "dataforseo"
