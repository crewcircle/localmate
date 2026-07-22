"""GBP Media upload service — POST v4 media with sourceUrl (URL method).

Uses the URL method (sourceUrl) rather than the 3-step byte upload, since
Supabase public bucket URLs are already publicly accessible.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

GBP_MEDIA_BASE = "https://mybusiness.googleapis.com/v4"


async def upload_location_photo(
    access_token: str,
    gbp_account_id: str,
    gbp_location_id: str,
    source_url: str,
    category: str = "MENU",
) -> str:
    """Upload a photo to a GBP location via the Media API (URL method).

    POST v4 ``/accounts/{accountId}/locations/{locationId}/media`` with
    ``sourceUrl`` (public Supabase URL). Returns the GBP media resource name.
    """
    url = (
        f"{GBP_MEDIA_BASE}/accounts/{gbp_account_id}"
        f"/locations/{gbp_location_id}/media"
    )

    body = {
        "mediaFormat": "PHOTO",
        "locationAssociation": {"category": category},
        "sourceUrl": source_url,
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(url, json=body, headers=headers, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            return data.get("name", "")
    except httpx.HTTPError as e:
        logger.error("GBP upload_location_photo failed: %s", e)
        raise
