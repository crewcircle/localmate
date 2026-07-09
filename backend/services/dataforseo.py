import base64
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

BASE = "https://api.dataforseo.com/v3"


def _auth_header() -> dict[str, str]:
    token = base64.b64encode(
        f"{settings.dataforseo_login}:{settings.dataforseo_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {token}"}


async def get_local_rankings(
    keyword: str, location: str, client_suburb: str = ""
) -> dict:
    """Query DataForSEO Google organic SERP (live) for a keyword.

    Returns {keyword, position, url} on success or
    {keyword, position: None, url: None} if not found / API error.
    """
    location_name = (
        f"{client_suburb}, Australia" if client_suburb else f"{location}, Australia"
    )

    payload = [
        {
            "keyword": keyword,
            "location_name": location_name,
            "language_code": "en",
            "device": "mobile",
            "os": "android",
            "depth": 30,
        }
    ]

    headers = {
        **_auth_header(),
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE}/serp/google/organic/live/advanced",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error("DataForSEO API request failed for keyword '%s': %s", keyword, e)
        return {"keyword": keyword, "position": None, "url": None}

    try:
        tasks = data.get("tasks", [])
        if not tasks:
            logger.warning("No tasks returned for keyword '%s'", keyword)
            return {"keyword": keyword, "position": None, "url": None}

        result = tasks[0].get("result", [])
        if not result:
            logger.warning("No result items for keyword '%s'", keyword)
            return {"keyword": keyword, "position": None, "url": None}

        items = result[0].get("items", [])
        if not items:
            logger.info("Keyword '%s' not found in top 30 results", keyword)
            return {"keyword": keyword, "position": None, "url": None}

        organic = [it for it in items if it.get("type") == "organic"]
        if not organic:
            return {"keyword": keyword, "position": None, "url": None}

        first = organic[0]
        return {
            "keyword": keyword,
            "position": first.get("rank_absolute"),
            "url": first.get("url"),
        }
    except (KeyError, IndexError, TypeError) as e:
        logger.error(
            "Failed to parse DataForSEO response for keyword '%s': %s", keyword, e
        )
        return {"keyword": keyword, "position": None, "url": None}
