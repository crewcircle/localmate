"""Tests for menu image storage + platform propagation."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_store_image_uploads_to_bucket_and_inserts_row():
    """store_image uploads to Supabase storage, builds public URL, inserts menu_images row."""
    from services.menu_images import store_image

    db = MagicMock()
    # storage.from_(bucket).upload(path, bytes)
    storage_mock = MagicMock()
    bucket_mock = MagicMock()
    bucket_mock.upload.return_value = None
    bucket_mock.get_public_url.return_value = "https://cdn.supabase.co/menu-images/mi1/img.jpg"
    storage_mock.from_.return_value = bucket_mock
    db.storage = storage_mock
    # table insert
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{
            "id": "img1",
            "menu_item_id": "mi1",
            "storage_path": "mi1/img.jpg",
            "public_url": "https://cdn.supabase.co/menu-images/mi1/img.jpg",
        }]
    )

    with patch("services.menu_images.get_db", return_value=db), \
         patch("services.menu_images.settings") as mock_settings:
        mock_settings.menu_images_bucket = "menu-images"
        result = await store_image("mi1", b"fake-image-bytes", "img.jpg")

    assert result["id"] == "img1"
    assert result["storage_path"] == "mi1/img.jpg"
    assert "public_url" in result
    # Upload was called with the right path + bytes
    bucket_mock.upload.assert_called_once_with("mi1/img.jpg", b"fake-image-bytes")
    # Public URL was retrieved
    bucket_mock.get_public_url.assert_called_once_with("mi1/img.jpg")


@pytest.mark.asyncio
async def test_sync_image_to_platforms_calls_square_and_gbp():
    """sync_image_to_platforms calls Square create_catalog_image + GBP upload_location_photo
    and persists square_image_id + gbp_media_name."""
    from services.menu_images import sync_image_to_platforms

    menu_image = {
        "id": "img1",
        "menu_item_id": "mi1",
        "storage_path": "mi1/img.jpg",
        "public_url": "https://cdn.supabase.co/menu-images/mi1/img.jpg",
    }
    location = {
        "id": "loc1",
        "square_location_id": "SQ_LOC_1",
        "gbp_account_id": "acct1",
        "gbp_location_id": "loc_gbp_1",
    }
    client = {
        "id": "c1",
        "gbp_access_token": "enc_gbp_token",
        "square_access_token": "enc_sq_token",
        "square_refresh_token": "enc_sq_refresh",
    }

    db = MagicMock()
    # menu_item_links select → returns external_id
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"external_id": "SQ_OBJ_1"}
    )
    # menu_images update
    db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    # storage download for Square image upload
    storage_mock = MagicMock()
    bucket_mock = MagicMock()
    bucket_mock.download.return_value = b"image-bytes"
    storage_mock.from_.return_value = bucket_mock
    db.storage = storage_mock

    with patch("services.menu_images.get_db", return_value=db), \
         patch("services.menu_images.settings") as mock_settings, \
         patch("services.square_oauth.get_valid_token", new_callable=AsyncMock, return_value="sq_tok"), \
         patch("services.square_images.create_catalog_image", new_callable=AsyncMock, return_value="SQ_IMG_1"), \
         patch("services.gbp_media.upload_location_photo", new_callable=AsyncMock, return_value="media/123"), \
         patch("services.crypto.decrypt", return_value="gbp_tok"):
        mock_settings.menu_images_bucket = "menu-images"
        result = await sync_image_to_platforms(menu_image, location, client)

    assert result["square_image_id"] == "SQ_IMG_1"
    assert result["gbp_media_name"] == "media/123"
    # menu_images row was updated with the platform ids + synced_at
    update_data = db.table.return_value.update.call_args[0][0]
    assert update_data["square_image_id"] == "SQ_IMG_1"
    assert update_data["gbp_media_name"] == "media/123"
    assert "synced_at" in update_data


@pytest.mark.asyncio
async def test_sync_image_to_platforms_handles_missing_square_location():
    """When location has no square_location_id, Square sync is skipped gracefully."""
    from services.menu_images import sync_image_to_platforms

    menu_image = {
        "id": "img1",
        "menu_item_id": "mi1",
        "storage_path": "mi1/img.jpg",
        "public_url": "https://cdn.supabase.co/menu-images/mi1/img.jpg",
    }
    location = {
        "id": "loc1",
        "square_location_id": None,  # no Square
        "gbp_account_id": "acct1",
        "gbp_location_id": "loc_gbp_1",
    }
    client = {"id": "c1", "gbp_access_token": "enc_gbp_token"}

    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    with patch("services.menu_images.get_db", return_value=db), \
         patch("services.gbp_media.upload_location_photo", new_callable=AsyncMock, return_value="media/123"), \
         patch("services.crypto.decrypt", return_value="gbp_tok"):
        result = await sync_image_to_platforms(menu_image, location, client)

    assert result["square_image_id"] is None
    assert result["gbp_media_name"] == "media/123"
