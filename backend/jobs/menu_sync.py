import logging
import uuid
from datetime import datetime
import asyncio

import httpx

from db import get_db
from config import settings

logger = logging.getLogger(__name__)

GBP_BASE_URL = "https://mybusinessbusinessinformation.googleapis.com/v1"
GBP_MENU_ITEMS_ENDPOINT = GBP_BASE_URL + "/accounts/{account_id}/menuItems"

SQUARE_SANDBOX_BASE = "https://connect.squareupsandbox.com"
SQUARE_PRODUCTION_BASE = "https://connect.squareup.com"
SQUARE_CATALOG_ENDPOINT = "/v2/catalog/object"
SQUARE_API_VERSION = "2024-06-19"

RETRY_MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 5


def _square_base_url() -> str:
    if settings.square_environment == "production":
        return SQUARE_PRODUCTION_BASE
    return SQUARE_SANDBOX_BASE


# GBP Menu API v1: POST .../accounts/{account_id}/menuItems


async def _sync_gbp(client: dict, item: dict) -> dict:
    from services.crypto import decrypt  # lazy — avoids circular import at module level

    account_id = client.get("gbp_account_id", "")
    if not account_id:
        return {"synced": False, "message": "Client missing gbp_account_id"}

    gbp_token = client.get("gbp_access_token", "")
    if not gbp_token:
        return {"synced": False, "message": "Client missing gbp_access_token"}

    access_token = decrypt(gbp_token)
    url = GBP_MENU_ITEMS_ENDPOINT.format(account_id=account_id)

    body = {
        "name": item["name"],
        "description": item.get("description", ""),
        "price": f"{item['price_cents'] / 100.0:.2f}",
        "currency": "AUD",
    }

    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.post(
                    url,
                    json=body,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
                resp.raise_for_status()
            logger.info(
                "GBP menu item synced: %s (account=%s)", item["name"], account_id
            )
            return {"synced": True, "message": "Synced to GBP"}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500 and attempt < RETRY_MAX_ATTEMPTS - 1:
                logger.warning(
                    "GBP transient error %s (attempt %d/%d), retrying in %ds",
                    exc.response.status_code,
                    attempt + 1,
                    RETRY_MAX_ATTEMPTS,
                    RETRY_DELAY_SECONDS,
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            logger.error("GBP sync failed for %s: %s", item["name"], exc)
            return {"synced": False, "message": f"GBP API error: {exc}"}
        except Exception as exc:
            if attempt < RETRY_MAX_ATTEMPTS - 1:
                logger.warning(
                    "GBP error on attempt %d/%d: %s, retrying in %ds",
                    attempt + 1,
                    RETRY_MAX_ATTEMPTS,
                    exc,
                    RETRY_DELAY_SECONDS,
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            logger.error("GBP sync failed for %s: %s", item["name"], exc)
            return {"synced": False, "message": f"GBP sync error: {exc}"}

    return {"synced": False, "message": "GBP sync failed after retries"}


async def _sync_square(client: dict, item: dict) -> dict:
    base_url = _square_base_url()
    token = settings.square_access_token
    if not token:
        return {"synced": False, "message": "Square access token not configured"}

    url = f"{base_url}{SQUARE_CATALOG_ENDPOINT}"
    idempotency_key = str(uuid.uuid4())

    body = {
        "idempotency_key": idempotency_key,
        "object": {
            "type": "ITEM",
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
        },
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Square-Version": SQUARE_API_VERSION,
        "Content-Type": "application/json",
    }

    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.post(url, json=body, headers=headers, timeout=30.0)
                resp.raise_for_status()
            logger.info("Square catalog item synced: %s", item["name"])
            return {"synced": True, "message": "Synced to Square"}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500 and attempt < RETRY_MAX_ATTEMPTS - 1:
                logger.warning(
                    "Square transient error %s (attempt %d/%d), retrying in %ds",
                    exc.response.status_code,
                    attempt + 1,
                    RETRY_MAX_ATTEMPTS,
                    RETRY_DELAY_SECONDS,
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            logger.error("Square sync failed for %s: %s", item["name"], exc)
            return {"synced": False, "message": f"Square API error: {exc}"}
        except Exception as exc:
            if attempt < RETRY_MAX_ATTEMPTS - 1:
                logger.warning(
                    "Square error on attempt %d/%d: %s, retrying in %ds",
                    attempt + 1,
                    RETRY_MAX_ATTEMPTS,
                    exc,
                    RETRY_DELAY_SECONDS,
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            logger.error("Square sync failed for %s: %s", item["name"], exc)
            return {"synced": False, "message": f"Square sync error: {exc}"}

    return {"synced": False, "message": "Square sync failed after retries"}


async def sync_to_platform(platform: str, client: dict, item: dict) -> dict:
    """Dispatch menu item sync to target platform. Returns {"synced": bool, "message": str}."""
    try:
        if platform == "gbp":
            return await _sync_gbp(client, item)
        elif platform == "square":
            return await _sync_square(client, item)
        elif platform == "website":
            return {
                "synced": False,
                "message": "Website CMS sync not yet implemented in MVP",
            }
        elif platform in ("ubereats", "doordash", "lightspeed"):
            return {
                "synced": False,
                "message": f"{platform.title()} sync not yet implemented in MVP",
            }
        else:
            return {"synced": False, "message": f"Unknown target: {platform}"}
    except Exception as exc:
        logger.error("sync_to_platform failed for %s: %s", platform, exc)
        return {"synced": False, "message": str(exc)}


def log_sync_results(client_id: str, item: dict, targets: list, results: list) -> None:
    db = get_db()
    for target, result in zip(targets, results):
        synced = result.get("synced", False)
        db.table("menu_sync_log").insert(
            {
                "client_id": client_id,
                "item_name": item.get("name", ""),
                "price_cents": item.get("price_cents"),
                "target": target,
                "status": "synced" if synced else "failed",
                "error_message": None if synced else result.get("message", ""),
                "synced_at": datetime.utcnow().isoformat(),
            }
        ).execute()


async def sync_menu_item(client_id: str, item: dict) -> dict:
    db = get_db()
    resp = (
        db.table("clients").select("*").eq("id", client_id).maybe_single().execute()
    )
    client = resp.data if resp.data else None
    if not client:
        logger.error(f"Client not found: {client_id}")
        return {"status": "failed", "error": "Client not found"}

    targets = client.get("menu_sync_targets", [])
    if not targets:
        logger.info(f"No menu_sync_targets configured for client {client_id}")
        return {"status": "skipped", "reason": "No targets configured"}

    results = await asyncio.gather(
        *[sync_to_platform(target, client, item) for target in targets],
        return_exceptions=True,
    )

    cleaned: list[dict] = []
    for r in results:
        if isinstance(r, Exception):
            cleaned.append({"synced": False, "message": str(r)})
        else:
            cleaned.append(r)

    log_sync_results(client_id, item, targets, cleaned)
    return {"status": "completed", "targets": dict(zip(targets, cleaned))}
