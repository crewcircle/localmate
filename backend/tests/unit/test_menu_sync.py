"""Tests for menu item sync to Square."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_menu_item_synced_to_square():
    """Menu item is synced to Square catalog via API."""
    from jobs.menu_sync import _sync_square

    item = {
        "name": "Teeth Whitening",
        "price_cents": 19900,
        "description": "Professional teeth whitening treatment",
        "category": "dental",
    }

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with patch("jobs.menu_sync.settings") as mock_settings, \
         patch("jobs.menu_sync.httpx.AsyncClient", return_value=mock_client):
        mock_settings.square_access_token = "sq0access-token-stub"
        mock_settings.square_environment = "sandbox"

        result = await _sync_square(
            client={"id": "client-1"},
            item=item,
        )

    assert result["synced"] is True
    assert result["message"] == "Synced to Square"
