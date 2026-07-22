"""Menu sync engine — canonical store + bi-directional reconciliation.

Rewrite of the original one-way Sheets→GBP/Square pusher into a location-aware,
bi-directional sync engine with a canonical menu store. Loop prevention via
menu_item_links.last_synced_hash. Per-client Square OAuth tokens (no global
settings.square_access_token). Square catalog writes run inside the durable
process_menu_update arq task (C4).
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone

import httpx

from db import get_db

logger = logging.getLogger(__name__)

GBP_BASE_URL = "https://mybusinessbusinessinformation.googleapis.com/v1"
GBP_MENU_ITEMS_ENDPOINT = GBP_BASE_URL + "/accounts/{account_id}/menuItems"

RETRY_MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 5


# ---------------------------------------------------------------------------
# Content hash + canonical store
# ---------------------------------------------------------------------------

def compute_content_hash(item: dict) -> str:
    """sha256 of canonical fields: name|price_cents|description|category|active."""
    canonical = "|".join([
        str(item.get("name", "")),
        str(item.get("price_cents", 0)),
        str(item.get("description", "")),
        str(item.get("category", "")),
        str(item.get("active", True)),
    ])
    return hashlib.sha256(canonical.encode()).hexdigest()


async def upsert_canonical(
    client_id: str, location_id: str, item: dict, origin: str = "sheets"
) -> dict:
    """Insert/update menu_items keyed by (location_id, sheet_row_key).

    Sets content_hash, updated_at, origin. Returns the canonical row (with id).
    """
    db = get_db()
    content_hash = compute_content_hash(item)
    sheet_row_key = item.get("sheet_row_key") or item.get("name")

    # Try to find existing by (location_id, sheet_row_key)
    existing = (
        db.table("menu_items")
        .select("*")
        .eq("location_id", location_id)
        .eq("sheet_row_key", sheet_row_key)
        .maybe_single()
        .execute()
    )

    now = datetime.now(timezone.utc).isoformat()
    row_data = {
        "client_id": client_id,
        "location_id": location_id,
        "name": item["name"],
        "description": item.get("description", ""),
        "price_cents": item["price_cents"],
        "category": item.get("category", ""),
        "active": item.get("active", True),
        "content_hash": content_hash,
        "origin": origin,
        "sheet_row_key": sheet_row_key,
        "updated_at": now,
    }

    if existing and existing.data:
        resp = (
            db.table("menu_items")
            .update(row_data)
            .eq("id", existing.data["id"])
            .execute()
        )
        return resp.data[0] if resp.data else existing.data
    else:
        resp = db.table("menu_items").insert(row_data).execute()
        return resp.data[0] if resp.data else {}


# ---------------------------------------------------------------------------
# Reconciliation (outbound push)
# ---------------------------------------------------------------------------

async def _retry_push(label: str, coro_fn):
    """Run ``coro_fn()`` with bounded retry; return its result or a failure dict.

    Retries on a 5xx ``HTTPStatusError`` (or any other exception) up to
    ``RETRY_MAX_ATTEMPTS``. Non-retryable HTTP errors and exhausted retries
    return ``{"synced": False, "message": ...}`` with the platform ``label``.
    """
    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            return await coro_fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500 and attempt < RETRY_MAX_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            return {"synced": False, "message": f"{label} API error: {exc}"}
        except Exception as exc:
            if attempt < RETRY_MAX_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY_SECONDS)
                continue
            return {"synced": False, "message": f"{label} sync error: {exc}"}
    return {"synced": False, "message": f"{label} sync failed after retries"}


async def _push_to_square(
    location: dict, client: dict, menu_item: dict, link: dict | None
) -> dict:
    """Push a menu item to Square catalog via per-client OAuth token."""
    from services.square_oauth import get_valid_token
    from services.square_catalog import upsert_item as square_upsert

    square_location_id = location.get("square_location_id")
    if not square_location_id:
        return {"synced": False, "message": "Location missing square_location_id"}

    try:
        access_token = await get_valid_token(client)
    except Exception as e:
        return {"synced": False, "message": f"Square token error: {e}"}

    external_id = link.get("external_id") if link else None
    external_version = link.get("external_version") if link else None

    async def _do() -> dict:
        result = await square_upsert(
            access_token,
            square_location_id,
            menu_item,
            external_id=external_id,
            external_version=external_version,
        )
        return {
            "synced": True,
            "message": "Synced to Square",
            "external_id": result.get("id"),
            "external_version": result.get("version"),
        }

    return await _retry_push("Square", _do)


async def _push_to_gbp(
    location: dict, client: dict, menu_item: dict, link: dict | None
) -> dict:
    """Push a menu item to GBP Menu API v1 using location's gbp_account_id."""
    from services.crypto import decrypt

    account_id = location.get("gbp_account_id")
    if not account_id:
        return {"synced": False, "message": "Location missing gbp_account_id"}

    gbp_token = client.get("gbp_access_token", "")
    if not gbp_token:
        return {"synced": False, "message": "Client missing gbp_access_token"}

    access_token = decrypt(gbp_token)
    url = GBP_MENU_ITEMS_ENDPOINT.format(account_id=account_id)

    body = {
        "name": menu_item["name"],
        "description": menu_item.get("description", ""),
        "price": f"{menu_item['price_cents'] / 100.0:.2f}",
        "currency": "AUD",
    }

    async def _do() -> dict:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )
            resp.raise_for_status()
        return {"synced": True, "message": "Synced to GBP"}

    return await _retry_push("GBP", _do)


async def reconcile_item(
    location: dict,
    client: dict,
    menu_item: dict,
    skip_platform: str | None = None,
) -> dict:
    """Reconcile a canonical menu item to its configured sync targets.

    For each target in ``location['menu_sync_targets']``:
    - Read the menu_item_links row for (menu_item, platform)
    - Skip if ``last_synced_hash == content_hash`` (loop guard)
    - Else push via the platform service and store external_id + last_synced_hash

    ``skip_platform`` excludes a platform from the push (used by
    ``apply_square_inbound`` to avoid echoing back to Square).

    Returns ``{"targets": {target: {"synced": bool, "message": str}}}``.
    """
    db = get_db()
    targets = location.get("menu_sync_targets", [])
    content_hash = menu_item.get("content_hash") or compute_content_hash(menu_item)

    results: dict[str, dict] = {}
    for target in targets:
        if target == skip_platform:
            results[target] = {"synced": True, "message": "Skipped (source platform)"}
            continue

        # Read existing link
        link_resp = (
            db.table("menu_item_links")
            .select("*")
            .eq("menu_item_id", menu_item["id"])
            .eq("platform", target)
            .maybe_single()
            .execute()
        )
        link = link_resp.data if link_resp.data else None
        last_synced_hash = link.get("last_synced_hash") if link else None

        # Loop guard: skip if hash matches
        if last_synced_hash == content_hash:
            results[target] = {"synced": True, "message": "Already in sync (hash match)"}
            continue

        # Push to platform
        if target == "square":
            result = await _push_to_square(location, client, menu_item, link)
        elif target == "gbp":
            result = await _push_to_gbp(location, client, menu_item, link)
        elif target == "website":
            result = {"synced": False, "message": "Website CMS sync not yet implemented"}
        elif target in ("ubereats", "doordash", "lightspeed"):
            result = {"synced": False, "message": f"{target.title()} sync not yet implemented"}
        else:
            result = {"synced": False, "message": f"Unknown target: {target}"}

        # Store link with external_id + last_synced_hash on success
        if result.get("synced"):
            link_data: dict = {
                "last_synced_hash": content_hash,
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
            }
            if result.get("external_id"):
                link_data["external_id"] = result["external_id"]
            if result.get("external_version") is not None:
                link_data["external_version"] = result["external_version"]

            if link:
                db.table("menu_item_links").update(link_data).eq("id", link["id"]).execute()
            else:
                link_data["menu_item_id"] = menu_item["id"]
                link_data["platform"] = target
                db.table("menu_item_links").insert(link_data).execute()

        results[target] = result

    # Log results with location_id (C6)
    log_sync_results(
        client["id"],
        location.get("id"),
        menu_item,
        list(results.keys()),
        list(results.values()),
    )

    return {"targets": results}


# ---------------------------------------------------------------------------
# Sync entry points
# ---------------------------------------------------------------------------

def log_sync_results(
    client_id: str,
    location_id: str | None,
    item: dict,
    targets: list,
    results: list,
) -> None:
    """Write per-target results to menu_sync_log (with location_id per C6)."""
    db = get_db()
    for target, result in zip(targets, results):
        synced = result.get("synced", False)
        row: dict = {
            "client_id": client_id,
            "item_name": item.get("name", ""),
            "price_cents": item.get("price_cents"),
            "target": target,
            "status": "synced" if synced else "failed",
            "error_message": None if synced else result.get("message", ""),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        if location_id:
            row["location_id"] = location_id
        db.table("menu_sync_log").insert(row).execute()


async def sync_menu_item(
    client_id: str,
    location_id: str | None = None,
    item: dict | None = None,
    origin: str = "sheets",
) -> dict:
    """Sync a menu item: upsert canonical + reconcile to targets.

    New signature: ``sync_menu_item(client_id, location_id, item, origin='sheets')``.
    Backward-compat: ``sync_menu_item(client_id, item)`` resolves the client's
    ``is_default`` location.
    """
    # Backward-compat: sync_menu_item(client_id, item) — 2 positional args
    if item is None and location_id is not None:
        item = location_id  # type: ignore[assignment]
        location_id = None

    db = get_db()

    # Load client
    resp = (
        db.table("clients")
        .select("*")
        .eq("id", client_id)
        .maybe_single()
        .execute()
    )
    client = resp.data if resp.data else None
    if not client:
        logger.error("Client not found: %s", client_id)
        return {"status": "failed", "error": "Client not found"}

    # Resolve location
    if location_id is None:
        # Default location (backward-compat)
        loc_resp = (
            db.table("locations")
            .select("*")
            .eq("client_id", client_id)
            .eq("is_default", True)
            .maybe_single()
            .execute()
        )
        if not loc_resp.data:
            # Fall back to first location
            loc_resp = (
                db.table("locations")
                .select("*")
                .eq("client_id", client_id)
                .limit(1)
                .execute()
            )
        if not loc_resp.data:
            return {"status": "skipped", "reason": "No location configured"}
        location = loc_resp.data[0] if isinstance(loc_resp.data, list) else loc_resp.data
    else:
        loc_resp = (
            db.table("locations")
            .select("*")
            .eq("id", location_id)
            .maybe_single()
            .execute()
        )
        location = loc_resp.data if loc_resp.data else None
        if not location:
            return {"status": "failed", "error": "Location not found"}

    # Upsert canonical
    menu_item = await upsert_canonical(client_id, location["id"], item, origin)

    # Reconcile
    result = await reconcile_item(location, client, menu_item)

    return {"status": "completed", "targets": result.get("targets", {})}


# ---------------------------------------------------------------------------
# Square inbound (bi-directional)
# ---------------------------------------------------------------------------

async def apply_square_inbound(client_id: str, changed_objects: list[dict]) -> dict:
    """Apply Square catalog changes to the canonical store.

    For each changed Square ITEM object:
    1. Find the menu_item_links row by external_id (platform='square')
    2. Resolve the canonical item + location
    3. upsert_canonical(origin='square') with the mapped content
    4. Set Square's last_synced_hash to the new hash (no echo back to Square)
    5. reconcile_item to push to OTHER targets only (skip_platform='square')

    Returns ``{"applied": int}``.
    """
    from services.square_catalog import square_object_to_canonical

    db = get_db()
    applied = 0

    for obj in changed_objects:
        if obj.get("type") != "ITEM":
            continue

        external_id = obj.get("id")
        if not external_id:
            continue

        # Find link by external_id
        link_resp = (
            db.table("menu_item_links")
            .select("*, menu_items(*)")
            .eq("platform", "square")
            .eq("external_id", external_id)
            .maybe_single()
            .execute()
        )

        if not link_resp.data:
            logger.info("Square inbound: no existing link for %s, skipping", external_id)
            continue

        link = link_resp.data
        menu_item = link.get("menu_items")
        if not menu_item:
            continue

        # Map Square object to canonical item
        square_item = square_object_to_canonical(obj)
        square_item["sheet_row_key"] = menu_item.get("sheet_row_key") or square_item["name"]

        new_hash = compute_content_hash(square_item)

        # Skip if already synced (echo prevention — should not happen since we
        # set last_synced_hash before reconcile, but guard against re-delivery)
        if link.get("last_synced_hash") == new_hash:
            continue

        location_id = menu_item["location_id"]

        # Upsert canonical with origin='square'
        updated_item = await upsert_canonical(client_id, location_id, square_item, origin="square")

        # Set Square's last_synced_hash to the new hash (no echo back)
        db.table("menu_item_links").update({
            "last_synced_hash": new_hash,
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "external_version": obj.get("version"),
        }).eq("id", link["id"]).execute()

        # Reconcile to OTHER targets only (skip Square)
        loc_resp = (
            db.table("locations")
            .select("*")
            .eq("id", location_id)
            .maybe_single()
            .execute()
        )
        client_resp = (
            db.table("clients")
            .select("*")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        if loc_resp.data and client_resp.data:
            await reconcile_item(loc_resp.data, client_resp.data, updated_item, skip_platform="square")

        applied += 1

    return {"applied": applied}
