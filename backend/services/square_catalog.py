"""Square Catalog API service — upsert, search, delete (httpx, no SDK).

Deterministic idempotency keys prevent duplicate catalog objects on re-sync.
search_changed drives the inbound reconciliation watermark flow.
"""

import logging
import uuid

import httpx

from services.square_oauth import square_base_url, SQUARE_API_VERSION

logger = logging.getLogger(__name__)


def _headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Square-Version": SQUARE_API_VERSION,
        "Content-Type": "application/json",
    }


async def upsert_item(
    access_token: str,
    square_location_id: str,
    item: dict,
    external_id: str | None = None,
    external_version: int | None = None,
) -> dict:
    """Upsert a Square Catalog ITEM via POST /v2/catalog/object.

    When ``external_id`` is provided, reuses it as the object ``id`` (update, not
    create) and passes ``external_version`` for optimistic concurrency. The
    idempotency key is deterministic: ``f"{menu_item_id}:square:{content_hash}"``
    so retries/re-syncs never create duplicates.

    ``present_at_all_locations=false`` + ``present_at_location_ids`` scopes the
    item to the venue.

    Returns ``{"id": str, "version": int}`` from the Square response.
    """
    url = f"{square_base_url()}/v2/catalog/object"

    menu_item_id = item.get("id", "")
    content_hash = item.get("content_hash", "")
    if menu_item_id and content_hash:
        idempotency_key = f"{menu_item_id}:square:{content_hash}"
    elif menu_item_id:
        idempotency_key = f"{menu_item_id}:square"
    else:
        idempotency_key = str(uuid.uuid4())

    obj: dict = {
        "type": "ITEM",
        "present_at_all_locations": False,
        "present_at_location_ids": [square_location_id],
        "item_data": {
            "name": item["name"],
            "description": item.get("description", ""),
            "variations": [
                {
                    "type": "ITEM_VARIATION",
                    "item_variation_data": {
                        "name": "Regular",
                        "price_money": {
                            "amount": item["price_cents"],
                            "currency": "AUD",
                        },
                        "pricing_type": "FIXED_PRICING",
                    },
                }
            ],
        },
    }

    if external_id:
        obj["id"] = external_id
        if external_version is not None:
            obj["version"] = external_version
    else:
        obj["id"] = "#temp"  # Square client-side temp id for create

    body = {
        "idempotency_key": idempotency_key,
        "object": obj,
    }

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(url, json=body, headers=_headers(access_token), timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            catalog_obj = data.get("catalog_object", {})
            return {
                "id": catalog_obj.get("id"),
                "version": catalog_obj.get("version"),
            }
    except httpx.HTTPError as e:
        logger.error("Square catalog upsert failed for %s: %s", item.get("name"), e)
        raise


async def search_changed(access_token: str, begin_time: str | None) -> dict:
    """Search for catalog changes since ``begin_time`` via POST /v2/catalog/search.

    ``begin_time`` is exclusive. ``include_deleted_objects=true`` catches
    deletions. Returns ``{"objects": [...], "latest_time": str | None}``.
    """
    url = f"{square_base_url()}/v2/catalog/search"

    body: dict = {
        "include_deleted_objects": True,
        "include_related_objects": False,
    }
    if begin_time:
        body["begin_time"] = begin_time

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(url, json=body, headers=_headers(access_token), timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            return {
                "objects": data.get("objects", []),
                "latest_time": data.get("latest_time"),
            }
    except httpx.HTTPError as e:
        logger.error("Square catalog search failed: %s", e)
        raise


async def delete_item(access_token: str, external_id: str) -> None:
    """Delete a Square Catalog object by id."""
    url = f"{square_base_url()}/v2/catalog/object/{external_id}"

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.delete(url, headers=_headers(access_token), timeout=30.0)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("Square catalog delete failed for %s: %s", external_id, e)
        raise


def square_object_to_canonical(obj: dict) -> dict:
    """Map a Square Catalog ITEM object to our canonical item dict."""
    item_data = obj.get("item_data", {})
    variations = item_data.get("variations", [])
    first_variation = variations[0] if variations else {}
    price_money = first_variation.get("item_variation_data", {}).get("price_money", {})

    return {
        "name": item_data.get("name", ""),
        "description": item_data.get("description", ""),
        "price_cents": price_money.get("amount", 0),
        "category": "",
        "active": not obj.get("is_deleted", False),
    }
