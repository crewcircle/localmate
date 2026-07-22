"""Tests for durable outbound wrapper tasks (Phase 0) — all five integrations."""
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from arq import Retry


def _client_db(client):
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=client
    )
    return db


@pytest.mark.asyncio
async def test_send_sms_task_success():
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock, return_value={"sent": True, "sid": "SM1"}):
        result = await task_queue.send_sms_task({"job_try": 1}, "+61400000000", "hi")
    assert result["sent"] is True


@pytest.mark.asyncio
async def test_send_sms_task_holiday_skip_is_not_a_failure():
    """A holiday skip returns {sent:False, skipped:True} and must be treated as success."""
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock,
               return_value={"sent": False, "skipped": True, "reason": "AU public holiday — skipped"}), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        result = await task_queue.send_sms_task({"job_try": 1}, "+61", "hi")
    assert result["skipped"] is True
    mock_dl.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_sms_task_soft_fail_raises_retry():
    """{sent: False} is a soft-fail — the task must raise arq.Retry so arq retries."""
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock, return_value={"sent": False, "reason": "boom"}), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(Retry):
            await task_queue.send_sms_task({"job_try": 1}, "+61", "hi")
        mock_dl.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_sms_task_dead_letters_on_final_try():
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock, return_value={"sent": False, "reason": "gone"}), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(RuntimeError):
            await task_queue.send_sms_task({"job_try": task_queue.MAX_TRIES}, "+61", "hi")
        mock_dl.assert_awaited_once()
        assert mock_dl.call_args[0][0] == "twilio"


@pytest.mark.asyncio
async def test_send_sms_task_exception_raises_retry_non_final():
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock, side_effect=ConnectionError("net")), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(Retry):
            await task_queue.send_sms_task({"job_try": 1}, "+61", "hi")
        mock_dl.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_sms_task_exception_dead_letters_on_final_try():
    import task_queue

    with patch("services.twilio_sms.send_sms", new_callable=AsyncMock, side_effect=ConnectionError("net")), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(ConnectionError):
            await task_queue.send_sms_task({"job_try": task_queue.MAX_TRIES}, "+61", "hi")
        mock_dl.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_email_task_dispatches_by_kind():
    import task_queue

    with patch("services.resend_email.send_email_strict", new_callable=AsyncMock, return_value={"id": "e1"}) as mock_send:
        await task_queue.send_email_task({"job_try": 1}, "welcome", "a@b.com", "Biz", "c1")
    mock_send.assert_awaited_once_with("welcome", "a@b.com", "Biz", "c1")


@pytest.mark.asyncio
async def test_send_email_task_unknown_kind_raises():
    import task_queue

    # send_email_strict raises ValueError for an unknown kind → dead-letter path.
    with patch("task_queue.record_dead_letter", new_callable=AsyncMock):
        with pytest.raises((ValueError, Retry)):
            await task_queue.send_email_task({"job_try": 1}, "nonexistent", "a@b.com", "Biz")


@pytest.mark.asyncio
async def test_send_email_task_transport_failure_raises_retry():
    """Resend transport failure must propagate (strict sender), not silently pass."""
    import task_queue

    with patch("services.resend_email.send_email_strict", new_callable=AsyncMock, side_effect=RuntimeError("resend down")), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(Retry):
            await task_queue.send_email_task({"job_try": 1}, "welcome", "a@b.com", "Biz", "c1")
        mock_dl.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_gbp_reply_task_loads_and_decrypts_token_in_worker():
    """The task takes IDs only; it loads the client and decrypts the token itself."""
    import task_queue

    db = _client_db({"id": "c1", "gbp_access_token": "ENC", "gbp_refresh_token": "ENCR"})

    with patch("task_queue.get_db", return_value=db), \
         patch("services.crypto.decrypt", side_effect=lambda t: "plain-" + t), \
         patch("services.gbp.post_review_reply", new_callable=AsyncMock, return_value=True) as mock_post:
        result = await task_queue.post_gbp_reply_task({"job_try": 1}, "c1", "loc", "rev", "reply")

    assert result is True
    # token passed to the service is the DECRYPTED value, resolved in-worker
    mock_post.assert_awaited_once_with("loc", "rev", "reply", "plain-ENC")


@pytest.mark.asyncio
async def test_post_gbp_reply_task_soft_fail_raises_retry():
    import task_queue

    db = _client_db({"id": "c1", "gbp_access_token": "ENC", "gbp_refresh_token": ""})

    with patch("task_queue.get_db", return_value=db), \
         patch("services.crypto.decrypt", side_effect=lambda t: "plain"), \
         patch("services.gbp.post_review_reply", new_callable=AsyncMock, return_value=False), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock):
        with pytest.raises(Retry):
            await task_queue.post_gbp_reply_task({"job_try": 1}, "c1", "loc", "rev", "reply")


@pytest.mark.asyncio
async def test_square_sync_task_loads_client_in_worker():
    """The task takes client_id only and loads the client (with secrets) itself."""
    import task_queue

    db = _client_db({"id": "c1", "square_access_token": "sq_secret"})

    with patch("task_queue.get_db", return_value=db), \
         patch("jobs.menu_sync._sync_square", new_callable=AsyncMock,
               return_value={"synced": True, "message": "Synced to Square"}) as mock_sync:
        result = await task_queue.square_sync_task({"job_try": 1}, "c1", {"name": "Latte"})

    assert result["synced"] is True
    # the loaded client (not an enqueued arg) is passed to the sync fn
    assert mock_sync.call_args[0][0]["id"] == "c1"


@pytest.mark.asyncio
async def test_square_sync_task_soft_fail_dead_letters_on_final():
    import task_queue

    db = _client_db({"id": "c1", "square_access_token": "sq"})

    with patch("task_queue.get_db", return_value=db), \
         patch("jobs.menu_sync._sync_square", new_callable=AsyncMock, return_value={"synced": False, "message": "bad"}), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(RuntimeError):
            await task_queue.square_sync_task({"job_try": task_queue.MAX_TRIES}, "c1", {"name": "Latte"})
        mock_dl.assert_awaited_once()
        assert mock_dl.call_args[0][0] == "square"


@pytest.mark.asyncio
async def test_dataforseo_task_success():
    import task_queue

    with patch("services.dataforseo.get_local_rankings_strict", new_callable=AsyncMock,
               return_value={"keyword": "dentist", "position": 3}):
        result = await task_queue.dataforseo_task({"job_try": 1}, "dentist", "Bondi")
    assert result["position"] == 3


@pytest.mark.asyncio
async def test_dataforseo_task_exception_dead_letters_on_final():
    import task_queue

    with patch("services.dataforseo.get_local_rankings_strict", new_callable=AsyncMock, side_effect=TimeoutError("slow")), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        with pytest.raises(TimeoutError):
            await task_queue.dataforseo_task({"job_try": task_queue.MAX_TRIES}, "dentist", "Bondi")
        mock_dl.assert_awaited_once()
        assert mock_dl.call_args[0][0] == "dataforseo"


@pytest.mark.asyncio
async def test_dataforseo_task_not_found_is_success():
    """A genuine 'not ranked in top 30' (position None) is a real answer, not a failure."""
    import task_queue

    with patch("services.dataforseo.get_local_rankings_strict", new_callable=AsyncMock,
               return_value={"keyword": "x", "position": None, "url": None}), \
         patch("task_queue.record_dead_letter", new_callable=AsyncMock) as mock_dl:
        result = await task_queue.dataforseo_task({"job_try": 1}, "x", "Bondi")
    assert result["position"] is None
    mock_dl.assert_not_awaited()


def test_credential_task_signatures_take_ids_only():
    """Regression guard (item 4): tasks that touch credentials must accept only
    stable IDs so no secret is ever serialized into Redis/AOF or arq's arg log."""
    import inspect
    import task_queue

    gbp_params = list(inspect.signature(task_queue.post_gbp_reply_task).parameters)
    # No access_token / token param — the token is loaded+decrypted in-worker.
    assert not any("token" in p for p in gbp_params), gbp_params
    assert "client_id" in gbp_params

    sq_params = list(inspect.signature(task_queue.square_sync_task).parameters)
    # Takes client_id, not the full client record (which carries secrets).
    assert "client_id" in sq_params
    assert "client" not in sq_params
