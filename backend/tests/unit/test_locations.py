"""Tests for locations API + menu webhook location routing + backfill."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Location-aware menu webhook
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_menu_update_with_location_id_routes_to_location():
    """POST /webhooks/menu-update/{client_id}/{location_id} includes location_id in payload."""
    from routers import webhooks

    payload = {"name": "Latte", "price": "4.50", "description": "", "category": "coffee"}
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "evt1"}])

    request = MagicMock()
    request.app.state.arq = MagicMock()
    request.app.state.arq.enqueue_job = AsyncMock()

    with patch("routers.webhooks.get_db", return_value=db):
        result = await webhooks.menu_update_location("c1", "loc1", payload, request)

    assert result["status"] == "received"
    # The persisted event payload includes location_id
    insert_arg = db.table.return_value.insert.call_args[0][0]
    assert insert_arg["payload"]["location_id"] == "loc1"
    assert insert_arg["payload"]["client_id"] == "c1"
    assert insert_arg["payload"]["origin"] == "sheets"


@pytest.mark.asyncio
async def test_menu_update_compat_path_has_null_location():
    """POST /webhooks/menu-update/{client_id} (compat) stores location_id=None in payload."""
    from routers import webhooks

    payload = {"name": "Latte", "price": "4.50"}
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "evt1"}])

    request = MagicMock()
    request.app.state.arq = MagicMock()
    request.app.state.arq.enqueue_job = AsyncMock()

    with patch("routers.webhooks.get_db", return_value=db):
        result = await webhooks.menu_update("c1", payload, request)

    assert result["status"] == "received"
    insert_arg = db.table.return_value.insert.call_args[0][0]
    assert insert_arg["payload"]["location_id"] is None


# ---------------------------------------------------------------------------
# resolve_client_from_location (C2 — locations table)
# ---------------------------------------------------------------------------

def test_resolve_client_from_location_uses_locations_table():
    """resolve_client_from_location resolves via locations.gbp_location_id (C2)."""
    from routers import webhooks

    db = MagicMock()

    def _table(name):
        chain = MagicMock()
        if name == "locations":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"client_id": "c1"}
            )
        elif name == "clients":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "c1", "business_name": "Test"}
            )
        return chain

    db.table.side_effect = _table

    with patch("routers.webhooks.get_db", return_value=db):
        client = webhooks.resolve_client_from_location(
            "accounts/ACCT1/locations/LOC_GBP_1/reviews/REV1"
        )

    assert client is not None
    assert client["id"] == "c1"


def test_resolve_client_from_location_returns_none_for_unknown():
    """resolve_client_from_location returns None when no location matches."""
    from routers import webhooks

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)

    with patch("routers.webhooks.get_db", return_value=db):
        client = webhooks.resolve_client_from_location(
            "accounts/ACCT1/locations/UNKNOWN/reviews/REV1"
        )

    assert client is None


# ---------------------------------------------------------------------------
# Locations API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_locations_returns_locations_for_client():
    """GET /locations?client_id=c1 returns the client's locations."""
    from routers.locations import list_locations

    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.is_.return_value.order.return_value.execute.return_value = MagicMock(
        data=[{"id": "loc1", "name": "Surry Hills", "client_id": "c1"}]
    )

    with patch("routers.locations.get_db", return_value=db):
        result = await list_locations(client_id="c1", auth={"sub": "anonymous"})

    assert len(result["locations"]) == 1
    assert result["locations"][0]["name"] == "Surry Hills"


@pytest.mark.asyncio
async def test_create_location_inserts_row():
    """POST /locations creates a new location."""
    from routers.locations import create_location

    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "loc_new", "name": "Bondi", "client_id": "c1"}]
    )

    with patch("routers.locations.get_db", return_value=db):
        result = await create_location(
            {"client_id": "c1", "name": "Bondi", "menu_sync_targets": ["square", "gbp"]},
            auth={"sub": "anonymous"},
        )

    assert result["location"]["name"] == "Bondi"
    insert_data = db.table.return_value.insert.call_args[0][0]
    assert insert_data["menu_sync_targets"] == ["square", "gbp"]


@pytest.mark.asyncio
async def test_update_location_updates_allowed_fields():
    """PATCH /locations/{id} updates only allowed fields (target toggles, Square pairing)."""
    from routers.locations import update_location

    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "loc1", "menu_sync_targets": ["square"], "square_location_id": "SQ_NEW"}]
    )

    with patch("routers.locations.get_db", return_value=db):
        result = await update_location(
            "loc1",
            {"menu_sync_targets": ["square"], "square_location_id": "SQ_NEW", "invalid_field": "hack"},
            auth={"sub": "anonymous"},
        )

    assert result["location"]["square_location_id"] == "SQ_NEW"
    update_data = db.table.return_value.update.call_args[0][0]
    assert "invalid_field" not in update_data
    assert "menu_sync_targets" in update_data
