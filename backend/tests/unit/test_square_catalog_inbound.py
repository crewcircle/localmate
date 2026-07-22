"""Tests for Square catalog inbound — webhook signature, search_changed, apply_square_inbound."""
import hashlib
import hmac
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


def _compute_square_sig(notification_url: str, raw_body: bytes, key: str) -> str:
    """Compute the Square webhook signature for testing."""
    message = notification_url.encode() + raw_body
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def test_verify_square_signature_rejects_bad_signature():
    """_verify_square_signature returns False for a wrong signature."""
    from routers.webhooks import _verify_square_signature
    from config import settings

    raw_body = b'{"merchant_id": "ML1"}'
    url = f"https://{settings.base_domain}/webhooks/square/catalog"
    bad_sig = "deadbeef" * 8

    assert _verify_square_signature(raw_body, bad_sig, url) is False


def test_verify_square_signature_accepts_valid_signature():
    """_verify_square_signature returns True for a correct signature."""
    from routers.webhooks import _verify_square_signature
    from config import settings

    raw_body = b'{"merchant_id": "ML1"}'
    url = f"https://{settings.base_domain}/webhooks/square/catalog"
    good_sig = _compute_square_sig(url, raw_body, settings.square_webhook_signature_key)

    assert _verify_square_signature(raw_body, good_sig, url) is True


# ---------------------------------------------------------------------------
# search_changed uses watermark
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_changed_uses_stored_watermark_as_begin_time():
    """search_changed passes the stored latest_time as begin_time."""
    from services.square_catalog import search_changed

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "objects": [{"type": "ITEM", "id": "SQ1"}],
        "latest_time": "2026-07-22T10:00:00.000Z",
    }

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = False
    mock_http.post.return_value = mock_resp

    with patch("services.square_catalog.httpx.AsyncClient", return_value=mock_http):
        result = await search_changed("sq_token", "2026-07-22T09:00:00.000Z")

    assert len(result["objects"]) == 1
    assert result["latest_time"] == "2026-07-22T10:00:00.000Z"
    call_body = mock_http.post.call_args[1]["json"]
    assert call_body["begin_time"] == "2026-07-22T09:00:00.000Z"
    assert call_body["include_deleted_objects"] is True


@pytest.mark.asyncio
async def test_search_changed_without_watermark():
    """search_changed works without a begin_time (initial sync)."""
    from services.square_catalog import search_changed

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"objects": [], "latest_time": "2026-07-22T10:00:00.000Z"}

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = False
    mock_http.post.return_value = mock_resp

    with patch("services.square_catalog.httpx.AsyncClient", return_value=mock_http):
        result = await search_changed("sq_token", None)

    call_body = mock_http.post.call_args[1]["json"]
    assert "begin_time" not in call_body
    assert result["latest_time"] == "2026-07-22T10:00:00.000Z"


# ---------------------------------------------------------------------------
# Square webhook handler — bad signature → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_square_catalog_webhook_rejects_bad_signature():
    """POST /webhooks/square/catalog returns 400 on bad signature."""
    from routers import webhooks
    from fastapi import HTTPException

    request = MagicMock()
    request.body = AsyncMock(return_value=b'{"merchant_id": "ML1"}')
    request.headers = {"x-square-hmacsha256-signature": "badsig"}

    with pytest.raises(HTTPException) as exc_info:
        await webhooks.square_catalog_webhook(request)

    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Square webhook handler — valid signature → search + apply + persist watermark
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_square_catalog_webhook_searches_and_applies():
    """Valid signature → resolve client, search_changed, apply_square_inbound,
    persist new latest_time watermark."""
    from routers import webhooks
    from config import settings

    raw_body = json.dumps({"merchant_id": "ML_MERCHANT_1"}).encode()
    url = f"https://{settings.base_domain}/webhooks/square/catalog"
    sig = _compute_square_sig(url, raw_body, settings.square_webhook_signature_key)

    request = MagicMock()
    request.body = AsyncMock(return_value=raw_body)
    request.headers = {"x-square-hmacsha256-signature": sig}

    db = MagicMock()
    state_chains = []

    def _table(name):
        chain = MagicMock()
        if name == "clients":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "c1", "square_merchant_id": "ML_MERCHANT_1",
                      "square_access_token": "enc", "square_refresh_token": "enc_r"}
            )
        elif name == "square_sync_state":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"latest_time": "2026-07-22T09:00:00.000Z"}
            )
            chain.upsert.return_value.execute.return_value = MagicMock(data=[])
            state_chains.append(chain)
        return chain

    db.table.side_effect = _table

    with patch("routers.webhooks.get_db", return_value=db), \
         patch("services.square_oauth.get_valid_token", new_callable=AsyncMock, return_value="sq_tok"), \
         patch("services.square_catalog.search_changed", new_callable=AsyncMock,
               return_value={"objects": [{"type": "ITEM", "id": "SQ1"}],
                             "latest_time": "2026-07-22T10:00:00.000Z"}), \
         patch("jobs.menu_sync.apply_square_inbound", new_callable=AsyncMock,
               return_value={"applied": 1}) as mock_apply:
        result = await webhooks.square_catalog_webhook(request)

    assert result["status"] == "received"
    mock_apply.assert_awaited_once()
    # Watermark persisted via upsert on square_sync_state
    # state_chains[0] = select (read watermark), state_chains[1] = upsert (persist)
    upsert_chain = next((c for c in state_chains if c.upsert.called), None)
    assert upsert_chain is not None
    upsert_data = upsert_chain.upsert.call_args[0][0]
    assert upsert_data["latest_time"] == "2026-07-22T10:00:00.000Z"


# ---------------------------------------------------------------------------
# square_object_to_canonical mapping
# ---------------------------------------------------------------------------

def test_square_object_to_canonical_maps_fields():
    """square_object_to_canonical maps Square ITEM to our canonical dict."""
    from services.square_catalog import square_object_to_canonical

    sq_obj = {
        "type": "ITEM",
        "id": "SQ_OBJ_1",
        "item_data": {
            "name": "Flat White",
            "description": "Double shot",
            "variations": [{
                "item_variation_data": {
                    "price_money": {"amount": 450, "currency": "AUD"}
                }
            }],
        },
    }

    result = square_object_to_canonical(sq_obj)
    assert result["name"] == "Flat White"
    assert result["description"] == "Double shot"
    assert result["price_cents"] == 450
    assert result["active"] is True


def test_square_object_to_canonical_handles_deleted():
    """Deleted Square objects map to active=False."""
    from services.square_catalog import square_object_to_canonical

    sq_obj = {
        "type": "ITEM",
        "id": "SQ_OBJ_1",
        "is_deleted": True,
        "item_data": {
            "name": "Old Item",
            "description": "",
            "variations": [],
        },
    }

    result = square_object_to_canonical(sq_obj)
    assert result["active"] is False
    assert result["price_cents"] == 0
