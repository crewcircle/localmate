import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

GOOGLE_OAUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GBP_API_BASE = "https://mybusiness.googleapis.com/v4"


def get_gbp_auth_url(client_id: str) -> str:
    """Build OAuth consent URL for client to connect their Google Business Profile."""
    redirect_uri = f"https://{settings.base_domain}/auth/gbp-callback"
    scopes = [
        "https://www.googleapis.com/auth/business.manage",
        "https://www.googleapis.com/auth/plus.business.read"
    ]
    params = {
        "client_id": settings.gbp_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": client_id
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_OAUTH_BASE}?{query}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange OAuth authorization code for access and refresh tokens."""
    redirect_uri = f"https://{settings.base_domain}/auth/gbp-callback"
    data = {
        "client_id": settings.gbp_client_id,
        "client_secret": settings.gbp_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error(f"GBP token exchange failed: {e}")
        raise


async def refresh_access_token(refresh_token: str) -> str:
    """Refresh expired GBP access token. Returns new access_token."""
    data = {
        "client_id": settings.gbp_client_id,
        "client_secret": settings.gbp_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
            resp.raise_for_status()
            return resp.json()["access_token"]
    except httpx.HTTPError as e:
        logger.error(f"GBP token refresh failed: {e}")
        raise


async def post_review_reply(
    location_id: str,
    review_id: str,
    reply: str,
    access_token: str
) -> bool:
    """Post a reply to a GBP review via the My Business API."""
    url = f"{GBP_API_BASE}/{location_id}/reviews/{review_id}/reply"
    headers = {"Authorization": f"Bearer {access_token}"}
    body = {"comment": reply}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.put(url, headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return True
    except httpx.HTTPError as e:
        logger.error(f"GBP post_review_reply failed: {e}")
        return False
