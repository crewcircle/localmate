"""Menu image upload endpoint (Phase 3 — C5 image ingestion contract).

Authenticated multipart upload endpoint. The alternative ingestion path (optional
Sheets ``image_url`` on the menu-update webhook) is handled by
``services/menu_images.py``.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from db import get_db
from middleware.auth import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/{location_id}/items/{item_id}/image")
async def upload_menu_image(
    location_id: str,
    item_id: str,
    file: UploadFile = File(...),
    auth: dict = Depends(require_auth),
):
    """Upload a menu item image (multipart).

    Stores in the Supabase ``menu-images`` bucket, inserts a ``menu_images`` row,
    and best-effort propagates to Square + GBP.
    """
    from services.menu_images import store_image, sync_image_to_platforms

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Empty file")

    # Verify the menu item belongs to this location
    db = get_db()
    item_resp = (
        db.table("menu_items")
        .select("*")
        .eq("id", item_id)
        .eq("location_id", location_id)
        .maybe_single()
        .execute()
    )
    if not item_resp.data:
        raise HTTPException(status_code=404, detail="Menu item not found")

    menu_image = await store_image(item_id, image_bytes, file.filename or "image.jpg")

    # Best-effort platform sync
    location = (
        db.table("locations")
        .select("*")
        .eq("id", location_id)
        .maybe_single()
        .execute()
    )
    client = (
        db.table("clients")
        .select("*")
        .eq("id", item_resp.data["client_id"])
        .maybe_single()
        .execute()
    )
    if location.data and client.data:
        try:
            await sync_image_to_platforms(menu_image, location.data, client.data)
        except Exception as e:
            logger.error("Image platform sync failed: %s", e)

    return {"status": "uploaded", "menu_image": menu_image}
