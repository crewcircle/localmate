"""Square Catalog Image upload service — multipart POST /v2/catalog/images (no SDK).

Builds multipart/form-data manually with httpx: part ``request`` = JSON, part
``file`` = image bytes. Square-Version 2024-06-19.
"""

import json
import logging
import uuid

import httpx

from services.square_oauth import square_base_url, SQUARE_API_VERSION

logger = logging.getLogger(__name__)


async def create_catalog_image(
    access_token: str,
    object_id: str,
    image_bytes: bytes,
    filename: str,
    caption: str = "",
) -> str:
    """Upload an image to Square and attach it to a CatalogItem.

    POST /v2/catalog/images as multipart/form-data:
      - part ``request``: JSON ``{idempotency_key, image:{...}, object_id, is_primary}``
      - part ``file``: image bytes

    Returns the Square CatalogImage id.
    """
    url = f"{square_base_url()}/v2/catalog/images"

    request_json = json.dumps({
        "idempotency_key": str(uuid.uuid4()),
        "image": {
            "type": "IMAGE",
            "id": "#temp",
            "image_data": {
                "name": filename,
                "caption": caption,
            },
        },
        "object_id": object_id,
        "is_primary": True,
    })

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Square-Version": SQUARE_API_VERSION,
    }

    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                url,
                headers=headers,
                data={"request": request_json},
                files={"file": (filename, image_bytes, "image/jpeg")},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            image_obj = data.get("image", {})
            return image_obj.get("id")
    except httpx.HTTPError as e:
        logger.error("Square create_catalog_image failed: %s", e)
        raise
