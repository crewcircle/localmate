"""Square OAuth + token management service.

Mirrors services/gbp.py + routers/auth.py GBP flow. Tokens are seller-scoped
(not per-location), so one token per client is stored on `clients`. The token
is Fernet-encrypted at rest (services/crypto.py).
"""

import logging
from datetime import datetime, timezone

import httpx

from config import settings

logger = logging.getLogger(__name__)

SQUARE_API_VERSION = "2024-06-19"

SQUARE_PRODUCTION_BASE = "https://connect.squareup.com"
SQUARE_SANDBOX_BASE = "https://connect.squareupsandbox.com"

SQUARE_AUTHORIZE_PATH = "/oauth2/authorize"
SQUARE_TOKEN_PATH = "/oauth2/token"


def square_base_url() -> str:
    """Return the Square Connect base URL for the configured environment."""
    if settings.square_environment == "production":
        return SQUARE_PRODUCTION_BASE
    return SQUARE_SANDBOX_BASE


def get_square_auth_url(client_id: str) -> str:
    """Build Square OAuth authorize URL for a client to connect their Square account.

    Scopes: ITEMS_READ ITEMS_WRITE (menu catalog) + MERCHANT_PROFILE_READ (list
    locations). state=client_id (mirrors GBP OAuth flow). Sandbox-aware host.
    """
    base = square_base_url()
    redirect_uri = f"https://{settings.base_domain}{settings.square_oauth_redirect_path}"
    scopes = "ITEMS_READ ITEMS_WRITE MERCHANT_PROFILE_READ"
    params = (
        f"client_id={settings.square_app_id}"
        f"&scope={scopes}"
        f"&redirect_uri={redirect_uri}"
        f"&state={client_id}"
        f"&session=false"
    )
    return f"{base}{SQUARE_AUTHORIZE_PATH}?{params}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange OAuth authorization code for access + refresh tokens."""
    url = f"{square_base_url()}{SQUARE_TOKEN_PATH}"
    data = {
        "client_id": settings.square_app_id,
        "client_secret": settings.square_app_secret,
        "code": code,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=data, timeout=15)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error("Square token exchange failed: %s", e)
        raise


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired Square access token. Returns the full token response."""
    url = f"{square_base_url()}{SQUARE_TOKEN_PATH}"
    data = {
        "client_id": settings.square_app_id,
        "client_secret": settings.square_app_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=data, timeout=15)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error("Square token refresh failed: %s", e)
        raise


async def list_locations(access_token: str) -> list[dict]:
    """List a merchant's Square locations. Used to populate per-venue square_location_ids."""
    url = f"{square_base_url()}/v2/locations"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Square-Version": SQUARE_API_VERSION,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json().get("locations", [])
    except httpx.HTTPError as e:
        logger.error("Square list_locations failed: %s", e)
        raise


async def get_valid_token(client: dict) -> str:
    """Resolve a valid Square access token for the client.

    Decrypts the stored token; if square_token_expires_at has passed (or the token
    is absent), refreshes via the stored refresh token, re-encrypts, and persists
    the new token + expiry on the clients row. Central helper used by the syncer
    and image service. Replaces the global settings.square_access_token path.
    """
    from services.crypto import decrypt, encrypt
    from db import get_db

    enc_access = client.get("square_access_token", "")
    enc_refresh = client.get("square_refresh_token", "")

    if not enc_access and not enc_refresh:
        raise RuntimeError(f"Client {client.get('id')} has no Square credentials")

    access_token = decrypt(enc_access) if enc_access else ""
    expires_at_str = client.get("square_token_expires_at")

    # Check if we need to refresh
    needs_refresh = not access_token
    if expires_at_str and access_token:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) >= expires_at:
                needs_refresh = True
        except (ValueError, TypeError):
            needs_refresh = True  # can't parse expiry — refresh to be safe

    if not needs_refresh:
        return access_token

    if not enc_refresh:
        # No refresh token — return whatever we have (may be expired)
        return access_token

    refresh_token = decrypt(enc_refresh)
    token_resp = await refresh_access_token(refresh_token)

    new_access = token_resp.get("access_token", "")
    new_refresh = token_resp.get("refresh_token", refresh_token)
    new_expiry = token_resp.get("expires_at")  # Square returns ISO 8601 expires_at

    # Persist refreshed tokens
    db = get_db()
    update: dict = {
        "square_access_token": encrypt(new_access),
        "square_refresh_token": encrypt(new_refresh),
    }
    if new_expiry:
        update["square_token_expires_at"] = new_expiry
    db.table("clients").update(update).eq("id", client["id"]).execute()

    return new_access
