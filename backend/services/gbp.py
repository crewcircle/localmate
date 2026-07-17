"""Google Business Profile service layer.

Migrated from v4 (mybusiness.googleapis.com/v4) to v1 APIs per Google's
deprecation notice.  Key endpoints by API:

  Business Information  – mybusinessbusinessinformation.googleapis.com/v1
  Notifications         – mybusinessnotifications.googleapis.com/v1
  Reviews (reply)       – mybusiness.googleapis.com/v4  (still current per
                          context7 /websites/developers_google_my-business)

OAuth scopes:
  business.manage            ← current, required
  plus.business.manage       ← deprecated, removed

Context7 docs consulted:
  /websites/developers_google_my-business
    • review-data / review reply endpoint (v4 confirmed current)
    • implement-oauth / scopes
    • notification-setup / accounts.updateNotificationSetting (v1)
"""

import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

GOOGLE_OAUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Business Information API v1 — locations, attributes, categories
BASE_API = "https://mybusinessbusinessinformation.googleapis.com/v1"

# Reviews API — confirmed v4 (context7: mybusiness/content/review-data)
GBP_REVIEWS_BASE = "https://mybusiness.googleapis.com/v4"

# Notifications API v1 — Pub/Sub notification settings
GBP_NOTIFICATIONS_BASE = "https://mybusinessnotifications.googleapis.com/v1"


def get_gbp_auth_url(client_id: str) -> str:
    """Build OAuth consent URL for client to connect their Google Business Profile."""
    redirect_uri = f"https://{settings.base_domain}/auth/gbp-callback"
    scopes = [
        "https://www.googleapis.com/auth/business.manage",
    ]
    params = {
        "client_id": settings.gbp_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": client_id,
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
        "redirect_uri": redirect_uri,
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
        "grant_type": "refresh_token",
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
    access_token: str,
) -> bool:
    """Post a reply to a GBP review via the My Business API.

    Uses v4 reviews endpoint (context7 confirms reviews are still on v4).
    location_id format: accounts/{accountId}/locations/{locationId}
    """
    url = f"{GBP_REVIEWS_BASE}/{location_id}/reviews/{review_id}/reply"
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
