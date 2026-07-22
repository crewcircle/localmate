"""Menu image storage + platform propagation service.

Images live in a Supabase storage bucket (``menu-images``, public read). This
service handles both ingestion paths (C5): the authenticated multipart upload
endpoint and the optional Sheets ``image_url`` on the menu-update webhook.
"""

import logging
from datetime import datetime, timezone

from db import get_db
from config import settings

logger = logging.getLogger(__name__)


async def store_image(menu_item_id: str, image_bytes: bytes, filename: str) -> dict:
    """Upload an image to the Supabase storage bucket and insert a menu_images row.

    Returns the menu_images row dict.
    """
    db = get_db()
    bucket = settings.menu_images_bucket
    storage_path = f"{menu_item_id}/{filename}"

    # Upload to Supabase storage
    db.storage.from_(bucket).upload(storage_path, image_bytes)

    # Build public URL
    public_url = db.storage.from_(bucket).get_public_url(storage_path)

    # Insert menu_images row
    resp = (
        db.table("menu_images")
        .insert({
            "menu_item_id": menu_item_id,
            "storage_path": storage_path,
            "public_url": public_url,
            "is_primary": True,
        })
        .execute()
    )
    return resp.data[0] if resp.data else {}


async def sync_image_to_platforms(
    menu_image: dict, location: dict, client: dict
) -> dict:
    """Propagate a stored menu image to Square and GBP.

    Calls ``square_images.create_catalog_image`` (needs the item's Square
    ``external_id`` from ``menu_item_links``) and
    ``gbp_media.upload_location_photo``. Persists ``square_image_id``,
    ``gbp_media_name``, ``synced_at`` on the menu_images row.

    Returns ``{"square_image_id": str | None, "gbp_media_name": str | None}``.
    """
    from services.square_oauth import get_valid_token
    from services.square_images import create_catalog_image
    from services.gbp_media import upload_location_photo
    from services.crypto import decrypt

    db = get_db()
    menu_item_id = menu_image["menu_item_id"]

    result: dict = {"square_image_id": None, "gbp_media_name": None}

    # --- Square image upload ---
    square_location_id = location.get("square_location_id")
    if square_location_id:
        try:
            link_resp = (
                db.table("menu_item_links")
                .select("external_id")
                .eq("menu_item_id", menu_item_id)
                .eq("platform", "square")
                .maybe_single()
                .execute()
            )
            external_id = (
                link_resp.data.get("external_id") if link_resp.data else None
            )

            if external_id:
                access_token = await get_valid_token(client)
                image_bytes = db.storage.from_(
                    settings.menu_images_bucket
                ).download(menu_image["storage_path"])
                square_image_id = await create_catalog_image(
                    access_token,
                    external_id,
                    image_bytes,
                    menu_image["storage_path"].split("/")[-1],
                )
                result["square_image_id"] = square_image_id
        except Exception as e:
            logger.error(
                "Square image sync failed for menu_item %s: %s", menu_item_id, e
            )

    # --- GBP media upload ---
    gbp_account_id = location.get("gbp_account_id")
    gbp_location_id = location.get("gbp_location_id")
    if gbp_account_id and gbp_location_id:
        try:
            enc_access = client.get("gbp_access_token", "")
            if enc_access:
                access_token = decrypt(enc_access)
                gbp_media_name = await upload_location_photo(
                    access_token,
                    gbp_account_id,
                    gbp_location_id,
                    menu_image["public_url"],
                )
                result["gbp_media_name"] = gbp_media_name
        except Exception as e:
            logger.error(
                "GBP image sync failed for menu_item %s: %s", menu_item_id, e
            )

    # Persist results
    update: dict = {"synced_at": datetime.now(timezone.utc).isoformat()}
    if result["square_image_id"]:
        update["square_image_id"] = result["square_image_id"]
    if result["gbp_media_name"]:
        update["gbp_media_name"] = result["gbp_media_name"]
    db.table("menu_images").update(update).eq("id", menu_image["id"]).execute()

    return result
