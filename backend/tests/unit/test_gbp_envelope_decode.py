"""Tests for GBP Pub/Sub push envelope decode + review fetch (Phase 0, C3)."""
import base64
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


def _make_envelope(notification: dict, message_id: str = "msg-123") -> dict:
    data = base64.b64encode(json.dumps(notification).encode()).decode()
    return {
        "message": {"messageId": message_id, "data": data},
        "subscription": "projects/p/subscriptions/s",
    }


def test_decode_pubsub_envelope_extracts_notification():
    from routers import webhooks

    notification = {
        "notificationType": "NEW_REVIEW",
        "location": "accounts/1/locations/2",
        "review": "accounts/1/locations/2/reviews/3",
    }
    decoded = webhooks.decode_pubsub_envelope(_make_envelope(notification, "m1"))
    assert decoded["message_id"] == "m1"
    assert decoded["notification"]["notificationType"] == "NEW_REVIEW"
    assert decoded["notification"]["review"] == "accounts/1/locations/2/reviews/3"


def test_decode_pubsub_envelope_missing_message_raises():
    from routers import webhooks

    with pytest.raises(ValueError):
        webhooks.decode_pubsub_envelope({"subscription": "x"})


def test_decode_pubsub_envelope_missing_message_id_raises():
    from routers import webhooks

    with pytest.raises(ValueError):
        webhooks.decode_pubsub_envelope({"message": {"data": ""}})


def test_decode_pubsub_envelope_bad_base64_raises():
    from routers import webhooks

    with pytest.raises(ValueError):
        webhooks.decode_pubsub_envelope({"message": {"messageId": "m", "data": "!!!not-base64!!!"}})


def test_decode_pubsub_envelope_empty_data_ok():
    from routers import webhooks

    decoded = webhooks.decode_pubsub_envelope({"message": {"messageId": "m", "data": ""}})
    assert decoded["notification"] == {}


@pytest.mark.asyncio
async def test_fetch_review_resource_gets_review_via_gbp_api():
    from routers import webhooks

    # tokens are stored Fernet-ENCRYPTED; fetch must decrypt them in-worker
    client = {"id": "c1", "gbp_access_token": "ENC_ACCESS", "gbp_refresh_token": "", "gbp_location_id": "2"}

    review_json = {"name": "accounts/1/locations/2/reviews/3", "comment": "Great!", "starRating": "FIVE"}
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=review_json)
    http = AsyncMock()
    http.get.return_value = resp
    http.__aenter__.return_value = http
    http.__aexit__.return_value = False

    with patch("routers.webhooks.resolve_client_from_location", return_value=client), \
         patch("services.crypto.decrypt", side_effect=lambda t: "tok" if t == "ENC_ACCESS" else ""), \
         patch("httpx.AsyncClient", return_value=http):
        result = await webhooks.fetch_review_resource("accounts/1/locations/2/reviews/3")

    assert result["comment"] == "Great!"
    http.get.assert_awaited_once()
    # Authorization header carries the DECRYPTED access token
    _, kwargs = http.get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer tok"


@pytest.mark.asyncio
async def test_fetch_review_resource_refreshes_on_401():
    """An expired access token → 401 → refresh (decrypted refresh token) + retry once."""
    import httpx
    from routers import webhooks

    client = {"id": "c1", "gbp_access_token": "ENC_ACCESS", "gbp_refresh_token": "ENC_REFRESH", "gbp_location_id": "2"}

    review_json = {"name": "accounts/1/locations/2/reviews/3", "comment": "Fixed!"}
    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    ok.json = MagicMock(return_value=review_json)

    unauthorized = MagicMock(status_code=401)
    err = httpx.HTTPStatusError("401", request=MagicMock(), response=unauthorized)
    fail = MagicMock()
    fail.raise_for_status = MagicMock(side_effect=err)

    http = AsyncMock()
    http.get.side_effect = [fail, ok]
    http.__aenter__.return_value = http
    http.__aexit__.return_value = False

    with patch("routers.webhooks.resolve_client_from_location", return_value=client), \
         patch("services.crypto.decrypt", side_effect=lambda t: {"ENC_ACCESS": "old", "ENC_REFRESH": "refresh"}[t]), \
         patch("services.gbp.refresh_access_token", new_callable=AsyncMock, return_value="newtok") as mock_refresh, \
         patch("httpx.AsyncClient", return_value=http):
        result = await webhooks.fetch_review_resource("accounts/1/locations/2/reviews/3")

    assert result["comment"] == "Fixed!"
    mock_refresh.assert_awaited_once_with("refresh")
    assert http.get.await_count == 2
    # retry used the refreshed token
    _, kwargs = http.get.call_args_list[1]
    assert kwargs["headers"]["Authorization"] == "Bearer newtok"


@pytest.mark.asyncio
async def test_fetch_review_resource_raises_on_persistent_failure():
    """A non-401 transport failure must RAISE (delivery stays retryable)."""
    import httpx
    from routers import webhooks

    client = {"id": "c1", "gbp_access_token": "ENC", "gbp_refresh_token": "", "gbp_location_id": "2"}

    resp = MagicMock(status_code=500)
    err = httpx.HTTPStatusError("500", request=MagicMock(), response=resp)
    fail = MagicMock()
    fail.raise_for_status = MagicMock(side_effect=err)
    http = AsyncMock()
    http.get.return_value = fail
    http.__aenter__.return_value = http
    http.__aexit__.return_value = False

    with patch("routers.webhooks.resolve_client_from_location", return_value=client), \
         patch("services.crypto.decrypt", side_effect=lambda t: "tok"), \
         patch("httpx.AsyncClient", return_value=http):
        with pytest.raises(httpx.HTTPError):
            await webhooks.fetch_review_resource("accounts/1/locations/2/reviews/3")


@pytest.mark.asyncio
async def test_fetch_review_resource_no_client_returns_empty():
    from routers import webhooks

    with patch("routers.webhooks.resolve_client_from_location", return_value=None):
        result = await webhooks.fetch_review_resource("accounts/1/locations/9/reviews/3")
    assert result == {}


@pytest.mark.asyncio
async def test_inbound_review_decodes_fetches_persists_enqueues():
    from routers import webhooks

    notification = {
        "notificationType": "NEW_REVIEW",
        "review": "accounts/1/locations/2/reviews/3",
    }
    envelope = _make_envelope(notification, "msg-abc")

    request = MagicMock()
    request.json = AsyncMock(return_value=envelope)
    request.app.state.arq = MagicMock()
    request.app.state.arq.enqueue_job = AsyncMock()

    db = MagicMock()
    # pre-fetch dedup lookup returns no existing row
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "evt-gbp"}])

    review_json = {"name": "accounts/1/locations/2/reviews/3", "comment": "Nice"}

    with patch("routers.webhooks.get_db", return_value=db), \
         patch("routers.webhooks.fetch_review_resource", new_callable=AsyncMock, return_value=review_json):
        result = await webhooks.inbound_review(request)

    assert result["status"] == "received"
    insert_arg = db.table.return_value.insert.call_args[0][0]
    assert insert_arg["provider"] == "gbp"
    assert insert_arg["idempotency_key"] == "msg-abc"
    assert insert_arg["payload"]["comment"] == "Nice"
    call = request.app.state.arq.enqueue_job.call_args
    assert call[0] == ("process_gbp_review", "evt-gbp")
    assert call[1]["_job_id"] == "process-webhook-evt-gbp"


@pytest.mark.asyncio
async def test_inbound_review_dedups_before_fetching_review():
    """A duplicate messageId must be deduped BEFORE any GBP fetch (item 3)."""
    from routers import webhooks

    envelope = _make_envelope({"notificationType": "NEW_REVIEW", "review": "accounts/1/locations/2/reviews/3"}, "dup-msg")

    request = MagicMock()
    request.json = AsyncMock(return_value=envelope)
    request.app.state.arq = MagicMock()
    request.app.state.arq.enqueue_job = AsyncMock()

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"id": "existing", "status": "done"}
    )

    mock_fetch = AsyncMock()
    with patch("routers.webhooks.get_db", return_value=db), \
         patch("routers.webhooks.fetch_review_resource", mock_fetch):
        result = await webhooks.inbound_review(request)

    assert result["status"] == "duplicate"
    # the provider fetch must NOT be called for a duplicate delivery
    mock_fetch.assert_not_awaited()
    request.app.state.arq.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_inbound_review_empty_fetch_returns_502_not_persisted():
    """An empty review resource must NOT be persisted+marked done — returns 502 (retryable)."""
    from routers import webhooks
    from fastapi import HTTPException

    envelope = _make_envelope({"notificationType": "NEW_REVIEW", "review": "accounts/1/locations/2/reviews/3"}, "empty-msg")

    request = MagicMock()
    request.json = AsyncMock(return_value=envelope)

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    with patch("routers.webhooks.get_db", return_value=db), \
         patch("routers.webhooks.fetch_review_resource", new_callable=AsyncMock, return_value={}):
        with pytest.raises(HTTPException) as exc:
            await webhooks.inbound_review(request)
    assert exc.value.status_code == 502
    db.table.return_value.insert.assert_not_called()


@pytest.mark.asyncio
async def test_inbound_review_fetch_failure_returns_502():
    """A fetch that RAISES keeps the delivery retryable (502), not a false 200."""
    from routers import webhooks
    from fastapi import HTTPException

    envelope = _make_envelope({"notificationType": "NEW_REVIEW", "review": "accounts/1/locations/2/reviews/3"}, "fail-msg")

    request = MagicMock()
    request.json = AsyncMock(return_value=envelope)

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    with patch("routers.webhooks.get_db", return_value=db), \
         patch("routers.webhooks.fetch_review_resource", new_callable=AsyncMock, side_effect=RuntimeError("gbp down")):
        with pytest.raises(HTTPException) as exc:
            await webhooks.inbound_review(request)
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_inbound_review_bad_envelope_returns_400():
    from routers import webhooks
    from fastapi import HTTPException

    request = MagicMock()
    request.json = AsyncMock(return_value={"garbage": True})

    with pytest.raises(HTTPException) as exc:
        await webhooks.inbound_review(request)
    assert exc.value.status_code == 400
