"""Tests for competitor website snapshot and change detection."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_website_snapshot_detects_change():
    """Detects changes when website content hash differs from previous snapshot."""
    from jobs.competitor_watch import detect_changes

    old_hash = "abc123oldhash"
    new_hash = "def456newhash"
    new_text = "We now offer emergency dental services 7 days a week in Bondi Junction."

    mock_last_resp = MagicMock()
    mock_last_resp.data = [
        {"content_hash": old_hash, "content_text": "Old content about dental services."}
    ]

    mock_insert_resp = MagicMock()
    mock_insert_resp.data = [{"id": "snap-new-123"}]

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value \
        .order.return_value.limit.return_value.execute.return_value = mock_last_resp
    mock_db.table.return_value.insert.return_value.execute.return_value = mock_insert_resp

    with patch("jobs.competitor_watch.get_db", return_value=mock_db), \
         patch("jobs.competitor_watch.snapshot_website", new_callable=AsyncMock) as mock_snap:
        mock_snap.return_value = (new_hash, new_text)

        result = await detect_changes(
            client_id="client-xyz",
            competitor_url="https://bondidental.com.au",
        )

    assert result is not None
    assert result["changed"] is True
    assert result["curr_text"] == new_text
    assert result["prev_text"] == "Old content about dental services."
    assert result["snapshot_id"] == "snap-new-123"
