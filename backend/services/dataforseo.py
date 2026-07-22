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


async def _query_rankings(keyword: str, location: str, client_suburb: str, *, strict: bool) -> dict:
    """Shared SERP query.

    When ``strict`` is True a transport/API failure RAISES (used by the durable
    arq task so it can retry / dead-letter). When False the failure is swallowed
    and a ``position: None`` result is returned (legacy fire-and-forget path).

    A genuine "not found in top 30" is NOT a failure in either mode — it returns
    ``position: None`` normally.
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
        if strict:
            raise
        return {"keyword": keyword, "position": None, "url": None}

    try:
        tasks = data.get("tasks", [])
        if not tasks:
            logger.warning("No tasks returned for keyword '%s'", keyword)
            if strict:
                raise RuntimeError(f"DataForSEO returned no tasks for '{keyword}'")
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
        if strict:
            raise
        return {"keyword": keyword, "position": None, "url": None}


async def get_local_rankings(
    keyword: str, location: str, client_suburb: str = ""
) -> dict:
    """Query DataForSEO Google organic SERP (live) for a keyword.

    Returns {keyword, position, url} on success or
    {keyword, position: None, url: None} if not found / API error.
    """
    return await _query_rankings(keyword, location, client_suburb, strict=False)


async def get_local_rankings_strict(
    keyword: str, location: str, client_suburb: str = ""
) -> dict:
    """Like :func:`get_local_rankings` but RAISES on transport/API failure.

    Used by the durable arq task (``dataforseo_task``) so a failed query is
    retried and eventually dead-lettered instead of masquerading as a valid
    ``position: None`` result. A genuine "not found in top 30" still returns
    ``position: None`` (that is a real answer, not a failure).
    """
    return await _query_rankings(keyword, location, client_suburb, strict=True)
