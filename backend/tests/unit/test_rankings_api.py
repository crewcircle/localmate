"""Tests for the rankings read API (Phase 4 — C7 for Phase 5 dashboard)."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_get_rankings_returns_rankings_with_map_position():
    """GET /rankings?location_id=... returns rankings including map_position."""
    from routers.seo import get_rankings

    mock_db = MagicMock()

    def _table(name):
        chain = MagicMock()
        if name == "locations":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"client_id": "c1"}
            )
        elif name == "rankings":
            chain.select.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value = MagicMock(
                data=[
                    {"keyword": "dentist bondi", "position": 3, "map_position": 2, "url": "https://sdc.com.au", "week_start": "2026-07-20"},
                    {"keyword": "dental clinic", "position": 7, "map_position": None, "url": "https://sdc.com.au", "week_start": "2026-07-20"},
                ]
            )
        return chain

    mock_db.table.side_effect = _table

    with patch("routers.seo.get_db", return_value=mock_db):
        result = await get_rankings(location_id="loc-1", auth={"sub": "anonymous"})

    assert len(result["rankings"]) == 2
    assert result["rankings"][0]["map_position"] == 2
    assert result["rankings"][1]["map_position"] is None


@pytest.mark.asyncio
async def test_get_rankings_404_for_unknown_location():
    """GET /rankings with an unknown location_id returns 404."""
    from routers.seo import get_rankings
    from fastapi import HTTPException

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data=None
    )

    with patch("routers.seo.get_db", return_value=mock_db):
        with pytest.raises(HTTPException) as exc_info:
            await get_rankings(location_id="unknown", auth={"sub": "anonymous"})

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_rankings_empty_for_client_with_no_rankings():
    """GET /rankings returns empty list when the client has no ranking data."""
    from routers.seo import get_rankings

    mock_db = MagicMock()

    def _table(name):
        chain = MagicMock()
        if name == "locations":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"client_id": "c1"}
            )
        elif name == "rankings":
            chain.select.return_value.eq.return_value.order.return_value.order.return_value.execute.return_value = MagicMock(
                data=[]
            )
        return chain

    mock_db.table.side_effect = _table

    with patch("routers.seo.get_db", return_value=mock_db):
        result = await get_rankings(location_id="loc-1", auth={"sub": "anonymous"})

    assert result["rankings"] == []
