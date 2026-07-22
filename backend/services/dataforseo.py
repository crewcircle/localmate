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


async def _post(endpoint: str, payload: list[dict], *, strict: bool) -> dict:
    """Shared DataForSEO POST with auth + error handling.

    Returns parsed JSON on success. On HTTP/transport error: raises (``strict``
    mode, for the durable arq wrapper) or returns ``{}`` (non-strict, for the
    legacy fire-and-forget job path).
    """
    headers = {
        **_auth_header(),
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE}/{endpoint}",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error("DataForSEO API request failed for endpoint '%s': %s", endpoint, e)
        if strict:
            raise
        return {}


def _location_name(location: str, client_suburb: str) -> str:
    return (
        f"{client_suburb}, Australia" if client_suburb else f"{location}, Australia"
    )


async def _query_rankings(keyword: str, location: str, client_suburb: str, *, strict: bool) -> dict:
    """Shared organic SERP query.

    When ``strict`` is True a transport/API failure RAISES (used by the durable
    arq task so it can retry / dead-letter). When False the failure is swallowed
    and a ``position: None`` result is returned (legacy fire-and-forget path).

    A genuine "not found in top 30" is NOT a failure in either mode — it returns
    ``position: None`` normally.
    """
    payload = [
        {
            "keyword": keyword,
            "location_name": _location_name(location, client_suburb),
            "language_code": "en",
            "device": "mobile",
            "os": "android",
            "depth": 30,
        }
    ]

    data = await _post("serp/google/organic/live/advanced", payload, strict=strict)

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


def _normalize_title(title: str) -> str:
    """Normalize a business title for fuzzy matching."""
    return (title or "").strip().lower()


async def _query_maps_rankings(
    keyword: str,
    location: str,
    client_suburb: str,
    business_name: str,
    place_id: str,
    *,
    strict: bool,
) -> dict:
    """Shared Google Maps / Local Pack SERP query.

    Matches the client business by ``place_id`` (from ``locations.place_id``)
    or fuzzy ``title == business_name``. Returns
    ``{keyword, map_position, place_id, matched}``.
    """
    payload = [
        {
            "keyword": keyword,
            "location_name": _location_name(location, client_suburb),
            "language_code": "en",
            "device": "mobile",
        }
    ]

    data = await _post("serp/google/maps/live/advanced", payload, strict=strict)

    not_found = {
        "keyword": keyword,
        "map_position": None,
        "place_id": None,
        "matched": False,
    }

    try:
        tasks = data.get("tasks", [])
        if not tasks:
            logger.warning("No tasks returned for Maps keyword '%s'", keyword)
            if strict:
                raise RuntimeError(f"DataForSEO Maps returned no tasks for '{keyword}'")
            return not_found

        result = tasks[0].get("result", [])
        if not result:
            logger.warning("No result items for Maps keyword '%s'", keyword)
            return not_found

        items = result[0].get("items", [])
        maps_items = [it for it in items if it.get("type") == "maps_search"]
        if not maps_items:
            logger.info("No maps_search items for keyword '%s'", keyword)
            return not_found

        # Match by place_id first (robust), then by normalized business name.
        matched_item = None
        if place_id:
            for it in maps_items:
                if it.get("place_id") == place_id:
                    matched_item = it
                    break

        if not matched_item and business_name:
            norm_biz = _normalize_title(business_name)
            for it in maps_items:
                if _normalize_title(it.get("title", "")) == norm_biz:
                    matched_item = it
                    break

        if matched_item:
            return {
                "keyword": keyword,
                "map_position": matched_item.get("rank_absolute"),
                "place_id": matched_item.get("place_id"),
                "matched": True,
            }

        return not_found
    except (KeyError, IndexError, TypeError) as e:
        logger.error(
            "Failed to parse DataForSEO Maps response for keyword '%s': %s", keyword, e
        )
        if strict:
            raise
        return not_found


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


async def get_maps_rankings(
    keyword: str,
    location: str,
    client_suburb: str = "",
    business_name: str = "",
    place_id: str = "",
) -> dict:
    """Query DataForSEO Google Maps live endpoint for a keyword.

    Matches the client business by ``place_id`` (preferred) or fuzzy
    ``title == business_name``. Returns
    ``{keyword, map_position, place_id, matched}`` on success or
    ``{keyword, map_position: None, place_id: None, matched: False}`` if not
    found / API error.
    """
    return await _query_maps_rankings(
        keyword, location, client_suburb, business_name, place_id, strict=False
    )


async def get_maps_rankings_strict(
    keyword: str,
    location: str,
    client_suburb: str = "",
    business_name: str = "",
    place_id: str = "",
) -> dict:
    """Like :func:`get_maps_rankings` but RAISES on transport/API failure.

    Used by the durable arq task (``dataforseo_maps_task``) so a failed Maps
    query is retried and eventually dead-lettered. A genuine "not matched in
    the local pack" still returns ``map_position: None`` normally.
    """
    return await _query_maps_rankings(
        keyword, location, client_suburb, business_name, place_id, strict=True
    )
