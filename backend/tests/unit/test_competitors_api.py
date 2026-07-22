"""Tests for the competitors read API (Phase 4 — C7 for Phase 5 dashboard)."""
import pytest
from unittest.mock import patch, MagicMock


def _db_with_location_and_snapshots(loc_client_id="c1", snapshots=None):
    """Build a mock db where locations lookup returns a client_id and
    competitor_snapshots returns the given snapshot rows."""
    mock_db = MagicMock()

    def _table(name):
        chain = MagicMock()
        if name == "locations":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"client_id": loc_client_id}
            )
        elif name == "competitor_snapshots":
            chain.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
                data=snapshots or []
            )
        return chain

    mock_db.table.side_effect = _table
    return mock_db


@pytest.mark.asyncio
async def test_get_competitor_snapshots_returns_structured_diff():
    """GET /competitors/snapshots?location_id=... returns snapshots including structured_diff.

    Per C8, client_id is derived from the location_id lookup — not accepted
    directly from the query string.
    """
    from routers.seo import get_competitor_snapshots

    snapshots = [
        {
            "id": "snap-1",
            "competitor_url": "https://comp.com",
            "content_hash": "abc",
            "brief_text": "Competitor dropped prices. Threat: MEDIUM",
            "threat_level": "MEDIUM",
            "structured_data": {
                "prices": [{"name": "Invisalign", "price": "3990", "currency": "AUD"}],
                "menu_items": [],
            },
            "structured_diff": [
                {"kind": "changed", "name": "Invisalign", "old": "4500", "new": "3990"},
            ],
            "captured_at": "2026-07-20T10:00:00Z",
        }
    ]
    mock_db = _db_with_location_and_snapshots(snapshots=snapshots)

    with patch("routers.seo.get_db", return_value=mock_db):
        result = await get_competitor_snapshots(location_id="loc-1", auth={"sub": "anonymous"})

    assert len(result["snapshots"]) == 1
    snap = result["snapshots"][0]
    assert snap["structured_diff"] is not None
    assert len(snap["structured_diff"]) == 1
    assert snap["structured_diff"][0]["kind"] == "changed"
    assert snap["structured_diff"][0]["old"] == "4500"
    assert snap["structured_diff"][0]["new"] == "3990"


@pytest.mark.asyncio
async def test_get_competitor_snapshots_empty():
    """GET /competitors/snapshots returns empty list when no snapshots exist."""
    from routers.seo import get_competitor_snapshots

    mock_db = _db_with_location_and_snapshots(snapshots=[])

    with patch("routers.seo.get_db", return_value=mock_db):
        result = await get_competitor_snapshots(location_id="loc-1", auth={"sub": "anonymous"})

    assert result["snapshots"] == []


@pytest.mark.asyncio
async def test_get_competitor_snapshots_404_for_unknown_location():
    """GET /competitors/snapshots with an unknown location_id returns 404 (C8)."""
    from routers.seo import get_competitor_snapshots
    from fastapi import HTTPException

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None
    )

    with patch("routers.seo.get_db", return_value=mock_db):
        with pytest.raises(HTTPException) as exc_info:
            await get_competitor_snapshots(location_id="unknown", auth={"sub": "anonymous"})

    assert exc_info.value.status_code == 404
