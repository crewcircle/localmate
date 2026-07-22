"""Tests for Square OAuth service — auth URL, token exchange, get_valid_token."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta


def test_get_square_auth_url_contains_scopes_and_state():
    """Auth URL includes the required scopes and state=client_id."""
    from services.square_oauth import get_square_auth_url

    url = get_square_auth_url("client-abc")
    assert "ITEMS_READ" in url
    assert "ITEMS_WRITE" in url
    assert "MERCHANT_PROFILE_READ" in url
    assert "state=client-abc" in url
    # Sandbox host when environment is sandbox
    assert "squareupsandbox.com" in url


def test_get_square_auth_url_production_host():
    """Production environment uses connect.squareup.com."""
    from services import square_oauth

    with patch.object(square_oauth.settings, "square_environment", "production"):
        url = square_oauth.get_square_auth_url("c1")
        assert "connect.squareup.com/oauth2/authorize" in url
        assert "squareupsandbox.com" not in url


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_posts_to_token_endpoint():
    """exchange_code_for_tokens POSTs to /oauth2/token with grant_type=authorization_code."""
    from services import square_oauth

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"access_token": "sq_at", "refresh_token": "sq_rt"}

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = False
    mock_http.post.return_value = mock_resp

    with patch("services.square_oauth.httpx.AsyncClient", return_value=mock_http):
        result = await square_oauth.exchange_code_for_tokens("the_code")

    assert result["access_token"] == "sq_at"
    call_args = mock_http.post.call_args
    assert "/oauth2/token" in call_args[0][0]
    assert call_args[1]["data"]["grant_type"] == "authorization_code"
    assert call_args[1]["data"]["code"] == "the_code"


@pytest.mark.asyncio
async def test_get_valid_token_refreshes_when_expired_and_persists():
    """get_valid_token refreshes an expired token and re-encrypts + persists."""
    from services import square_oauth

    # Client with expired token
    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    client = {
        "id": "c1",
        "square_access_token": "enc_old_access",
        "square_refresh_token": "enc_refresh",
        "square_token_expires_at": expired,
    }

    mock_db = MagicMock()

    with patch("db.get_db", return_value=mock_db), \
         patch("services.crypto.decrypt", side_effect=["old_access", "refresh_tok"]) as mock_decrypt, \
         patch("services.crypto.encrypt", side_effect=["enc_new_access", "enc_new_refresh"]) as mock_encrypt, \
         patch("services.square_oauth.refresh_access_token", new_callable=AsyncMock,
               return_value={"access_token": "new_access", "refresh_token": "new_refresh",
                             "expires_at": "2026-12-01T00:00:00Z"}):
        token = await square_oauth.get_valid_token(client)

    assert token == "new_access"
    # Decrypt was called for both access and refresh tokens
    assert mock_decrypt.call_count == 2
    # Encrypt was called for the new tokens
    assert mock_encrypt.call_count == 2
    # Persisted to clients table
    update_call = mock_db.table.return_value.update.call_args
    assert update_call is not None
    update_data = update_call[0][0]
    assert update_data["square_access_token"] == "enc_new_access"
    assert update_data["square_refresh_token"] == "enc_new_refresh"
    assert update_data["square_token_expires_at"] == "2026-12-01T00:00:00Z"


@pytest.mark.asyncio
async def test_get_valid_token_returns_cached_when_not_expired():
    """get_valid_token returns the decrypted token without refreshing when not expired."""
    from services import square_oauth

    future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    client = {
        "id": "c1",
        "square_access_token": "enc_access",
        "square_refresh_token": "enc_refresh",
        "square_token_expires_at": future,
    }

    with patch("services.crypto.decrypt", return_value="valid_access") as mock_decrypt, \
         patch("services.square_oauth.refresh_access_token", new_callable=AsyncMock) as mock_refresh:
        token = await square_oauth.get_valid_token(client)

    assert token == "valid_access"
    mock_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_locations_calls_v2_locations():
    """list_locations GETs /v2/locations with the access token."""
    from services import square_oauth

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"locations": [{"id": "SQ_LOC_1", "name": "Surry Hills"}]}

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = False
    mock_http.get.return_value = mock_resp

    with patch("services.square_oauth.httpx.AsyncClient", return_value=mock_http):
        result = await square_oauth.list_locations("sq_token")

    assert len(result) == 1
    assert result[0]["id"] == "SQ_LOC_1"
    call = mock_http.get.call_args
    assert "/v2/locations" in call[0][0]
    assert call[1]["headers"]["Authorization"] == "Bearer sq_token"
