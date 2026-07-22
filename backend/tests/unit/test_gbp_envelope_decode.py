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

    client = {"id": "c1", "gbp_access_token": "tok", "gbp_location_id": "2"}

    review_json = {"name": "accounts/1/locations/2/reviews/3", "comment": "Great!", "starRating": "FIVE"}
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=review_json)
    http = AsyncMock()
    http.get.return_value = resp
    http.__aenter__.return_value = http
    http.__aexit__.return_value = False

    with patch("routers.webhooks.resolve_client_from_location", return_value=client), \
         patch("httpx.AsyncClient", return_value=http):
        result = await webhooks.fetch_review_resource("accounts/1/locations/2/reviews/3")

    assert result["comment"] == "Great!"
    http.get.assert_awaited_once()
    # Authorization header carries the client's access token
    _, kwargs = http.get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer tok"


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
    request.app.state.arq.enqueue_job.assert_awaited_once_with("process_gbp_review", "evt-gbp")


@pytest.mark.asyncio
async def test_inbound_review_duplicate_message_id_deduped():
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

    with patch("routers.webhooks.get_db", return_value=db), \
         patch("routers.webhooks.fetch_review_resource", new_callable=AsyncMock, return_value={}):
        result = await webhooks.inbound_review(request)

    assert result["status"] == "duplicate"
    request.app.state.arq.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_inbound_review_bad_envelope_returns_400():
    from routers import webhooks
    from fastapi import HTTPException

    request = MagicMock()
    request.json = AsyncMock(return_value={"garbage": True})

    with pytest.raises(HTTPException) as exc:
        await webhooks.inbound_review(request)
    assert exc.value.status_code == 400
