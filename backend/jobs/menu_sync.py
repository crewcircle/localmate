import logging
from datetime import datetime
import asyncio
from db import get_db
from config import settings

logger = logging.getLogger(__name__)


def sync_to_platform(platform: str, client: dict, item: dict) -> dict:
    """Dispatch menu item sync to target platform.

    Supported platforms: gbp, square, website, ubereats, doordash, lightspeed.
    Returns {"status": "synced"} on success, {"status": "failed", "error": ...} on failure.
    """
    try:
        if platform == "gbp":
            try:
                from services.gbp import update_menu_item  # noqa: F401
                # TODO: call update_menu_item(client, item) when implemented
                return {"status": "failed", "error": "GBP menu API not implemented"}
            except ImportError:
                return {"status": "failed", "error": "GBP menu API not implemented"}
        elif platform == "square":
            return {"status": "failed", "error": "Square catalog API not implemented"}
        elif platform in ("website", "ubereats", "doordash", "lightspeed"):
            return {"status": "failed", "error": "Target not yet implemented"}
        else:
            return {"status": "failed", "error": f"Unknown target: {platform}"}
    except Exception as e:
        logger.error(f"sync_to_platform failed for {platform}: {e}")
        return {"status": "failed", "error": str(e)}


def log_sync_results(client_id: str, item: dict, targets: list[str], results: list[dict]) -> None:
    """Write sync results to the menu_sync_log table for each target."""
    db = get_db()
    for target, result in zip(targets, results):
        db.table("menu_sync_log").insert({
            "client_id": client_id,
            "item_name": item.get("name", ""),
            "price_cents": item.get("price_cents"),
            "target": target,
            "status": result.get("status", "failed"),
            "error_message": result.get("error"),
            "synced_at": datetime.utcnow().isoformat(),
        }).execute()


async def sync_menu_item(client_id: str, item: dict) -> dict:
    """Fetch client config and sync a menu item to all configured targets in parallel.

    Returns {"status": "completed", "targets": {...}} or an error dict.
    """
    db = get_db()
    resp = db.table("clients").select("*").eq("id", client_id).maybe_single().execute()
    client = resp.data if resp.data else None
    if not client:
        logger.error(f"Client not found: {client_id}")
        return {"status": "failed", "error": "Client not found"}

    targets = client.get("menu_sync_targets", [])
    if not targets:
        logger.info(f"No menu_sync_targets configured for client {client_id}")
        return {"status": "skipped", "reason": "No targets configured"}

    results = await asyncio.gather(
        *[asyncio.to_thread(sync_to_platform, target, client, item) for target in targets],
        return_exceptions=True,
    )

    cleaned: list[dict] = []
    for r in results:
        if isinstance(r, Exception):
            cleaned.append({"status": "failed", "error": str(r)})
        else:
            cleaned.append(r)

    log_sync_results(client_id, item, targets, cleaned)
    return {"status": "completed", "targets": dict(zip(targets, cleaned))}
