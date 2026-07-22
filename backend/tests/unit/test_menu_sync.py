"""Tests for menu sync — canonical store, reconciliation, loop guard, backward compat."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from jobs.menu_sync import compute_content_hash


# ---------------------------------------------------------------------------
# compute_content_hash
# ---------------------------------------------------------------------------

def test_content_hash_stable_for_same_fields():
    """Hash is identical for items with the same canonical fields."""
    item = {
        "name": "Flat White",
        "price_cents": 450,
        "description": "Double shot",
        "category": "coffee",
        "active": True,
    }
    h1 = compute_content_hash(item)
    h2 = compute_content_hash(dict(item))
    assert h1 == h2


def test_content_hash_changes_when_field_changes():
    """Hash differs when any canonical field changes."""
    item = {
        "name": "Flat White",
        "price_cents": 450,
        "description": "Double shot",
        "category": "coffee",
        "active": True,
    }
    h1 = compute_content_hash(item)
    item["price_cents"] = 500
    h2 = compute_content_hash(item)
    assert h1 != h2


def test_content_hash_ignores_non_canonical_fields():
    """Non-canonical fields (id, content_hash, origin) don't affect the hash."""
    item = {
        "name": "Latte",
        "price_cents": 500,
        "description": "",
        "category": "",
        "active": True,
    }
    h1 = compute_content_hash(item)
    item["id"] = "abc-123"
    item["content_hash"] = h1
    item["origin"] = "square"
    item["sheet_row_key"] = "row1"
    h2 = compute_content_hash(item)
    assert h1 == h2


# ---------------------------------------------------------------------------
# reconcile_item — loop guard + target filtering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconcile_skips_platform_when_hash_matches():
    """reconcile_item skips a platform when last_synced_hash == content_hash (loop guard)."""
    from jobs.menu_sync import reconcile_item

    menu_item = {
        "id": "mi1",
        "name": "Latte",
        "price_cents": 450,
        "description": "",
        "category": "",
        "active": True,
        "content_hash": "hash123",
    }
    location = {
        "id": "loc1",
        "menu_sync_targets": ["square", "gbp"],
        "square_location_id": "SQ1",
        "gbp_account_id": "acct1",
    }
    client = {"id": "c1"}

    # Both links already have the same hash — should skip both
    db = MagicMock()
    link_chain = MagicMock()
    link_chain.maybe_single.return_value.execute.return_value = MagicMock(
        data={"id": "link1", "last_synced_hash": "hash123"}
    )
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value = link_chain.maybe_single.return_value
    # For the update call
    db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    # For log_sync_results insert
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

    with patch("jobs.menu_sync.get_db", return_value=db):
        result = await reconcile_item(location, client, menu_item)

    assert result["targets"]["square"]["synced"] is True
    assert "hash match" in result["targets"]["square"]["message"].lower()
    assert result["targets"]["gbp"]["synced"] is True
    assert "hash match" in result["targets"]["gbp"]["message"].lower()


@pytest.mark.asyncio
async def test_reconcile_pushes_only_to_targets_whose_hash_differs():
    """reconcile_item pushes to a platform only when last_synced_hash != content_hash."""
    from jobs.menu_sync import reconcile_item

    menu_item = {
        "id": "mi1",
        "name": "Latte",
        "price_cents": 450,
        "description": "",
        "category": "",
        "active": True,
        "content_hash": "new_hash",
    }
    location = {
        "id": "loc1",
        "menu_sync_targets": ["square", "gbp"],
        "square_location_id": "SQ1",
        "gbp_account_id": "acct1",
    }
    client = {"id": "c1"}

    call_count = {"square": 0, "gbp": 0}

    async def mock_push_square(loc, cli, mi, link):
        call_count["square"] += 1
        return {"synced": True, "message": "Synced to Square",
                "external_id": "sq_obj1", "external_version": 2}

    async def mock_push_gbp(loc, cli, mi, link):
        call_count["gbp"] += 1
        return {"synced": True, "message": "Synced to GBP"}

    db = MagicMock()

    # Square link has old hash → should push
    # GBP link has matching hash → should skip
    link_data_map = {
        ("square",): {"id": "link_sq", "last_synced_hash": "old_hash"},
        ("gbp",): {"id": "link_gbp", "last_synced_hash": "new_hash"},
    }

    def _table(name):
        chain = MagicMock()
        if name == "menu_item_links":
            # Handle both select (read link) and update/insert (store link)
            def _eq(field, val):
                c = MagicMock()
                if (val,) in link_data_map:
                    c.maybe_single.return_value.execute.return_value = MagicMock(
                        data=link_data_map[(val,)]
                    )
                else:
                    c.maybe_single.return_value.execute.return_value = MagicMock(data=None)
                c.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                c.insert.return_value.execute.return_value = MagicMock(data=[])
                return c
            chain.select.return_value.eq.return_value.eq = _eq
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            chain.insert.return_value.execute.return_value = MagicMock(data=[])
        elif name == "menu_sync_log":
            chain.insert.return_value.execute.return_value = MagicMock(data=[])
        return chain

    db.table.side_effect = _table

    with patch("jobs.menu_sync.get_db", return_value=db), \
         patch("jobs.menu_sync._push_to_square", new_callable=AsyncMock, side_effect=mock_push_square), \
         patch("jobs.menu_sync._push_to_gbp", new_callable=AsyncMock, side_effect=mock_push_gbp):
        result = await reconcile_item(location, client, menu_item)

    assert call_count["square"] == 1  # pushed (hash differed)
    assert call_count["gbp"] == 0     # skipped (hash matched)


# ---------------------------------------------------------------------------
# Square uses deterministic idempotency + reuses stored external_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_square_upsert_uses_deterministic_key_and_reuses_external_id():
    """square_catalog.upsert_item uses a deterministic idempotency key and reuses
    the stored external_id (update, not create) when a link exists."""
    from services.square_catalog import upsert_item

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "catalog_object": {"id": "SQ_OBJ_1", "version": 5}
    }

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = False
    mock_http.post.return_value = mock_response

    item = {
        "id": "menu-item-uuid",
        "name": "Cappuccino",
        "price_cents": 420,
        "description": "Single shot",
        "content_hash": "abc123hash",
    }

    with patch("services.square_catalog.httpx.AsyncClient", return_value=mock_http):
        result = await upsert_item(
            "sq_token", "SQ_LOC_1", item,
            external_id="SQ_OBJ_1", external_version=4,
        )

    # Called with the existing id (update, not create)
    call_body = mock_http.post.call_args[1]["json"]
    assert call_body["object"]["id"] == "SQ_OBJ_1"
    assert call_body["object"]["version"] == 4
    # Deterministic idempotency key
    assert call_body["idempotency_key"] == "menu-item-uuid:square:abc123hash"
    # Scoped to the location
    assert call_body["object"]["present_at_all_locations"] is False
    assert call_body["object"]["present_at_location_ids"] == ["SQ_LOC_1"]
    # Returns id + version
    assert result["id"] == "SQ_OBJ_1"
    assert result["version"] == 5


# ---------------------------------------------------------------------------
# Backward-compat sync_menu_item(client_id, item)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backward_compat_sync_menu_item_resolves_default_location():
    """sync_menu_item(client_id, item) resolves the is_default location."""
    from jobs.menu_sync import sync_menu_item

    item = {
        "name": "Espresso",
        "price_cents": 350,
        "description": "",
        "category": "",
        "active": True,
    }

    db = MagicMock()

    def _table(name):
        chain = MagicMock()
        if name == "clients":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "c1", "menu_sync_targets": ["square"]}
            )
        elif name == "locations":
            # is_default lookup
            chain.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "loc1", "client_id": "c1", "is_default": True,
                      "menu_sync_targets": ["square"], "square_location_id": "SQ1"}
            )
        elif name == "menu_items":
            chain.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            chain.insert.return_value.execute.return_value = MagicMock(
                data=[{"id": "mi1", "name": "Espresso", "price_cents": 350,
                       "content_hash": compute_content_hash(item)}]
            )
        elif name == "menu_item_links":
            chain.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            chain.insert.return_value.execute.return_value = MagicMock(data=[])
        elif name == "menu_sync_log":
            chain.insert.return_value.execute.return_value = MagicMock(data=[])
        return chain

    db.table.side_effect = _table

    async def mock_push_square(loc, cli, mi, link):
        return {"synced": True, "message": "Synced to Square",
                "external_id": "sq1", "external_version": 1}

    with patch("jobs.menu_sync.get_db", return_value=db), \
         patch("jobs.menu_sync._push_to_square", new_callable=AsyncMock, side_effect=mock_push_square):
        # 2-arg backward-compat call
        result = await sync_menu_item("c1", item)

    assert result["status"] == "completed"
    assert result["targets"]["square"]["synced"] is True


# ---------------------------------------------------------------------------
# apply_square_inbound — no echo back
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_square_inbound_sets_square_hash_no_echo():
    """apply_square_inbound sets Square's last_synced_hash (no echo) and pushes
    to OTHER targets only (skip_platform='square')."""
    from jobs.menu_sync import apply_square_inbound

    changed_objects = [{
        "type": "ITEM",
        "id": "SQ_OBJ_1",
        "version": 7,
        "item_data": {
            "name": "Latte",
            "description": "Updated",
            "variations": [{
                "item_variation_data": {
                    "price_money": {"amount": 500, "currency": "AUD"}
                }
            }],
        },
    }]

    db = MagicMock()
    canonical_item = {
        "id": "mi1", "name": "Latte", "price_cents": 500,
        "description": "Updated", "category": "", "active": True,
        "content_hash": compute_content_hash({
            "name": "Latte", "price_cents": 500,
            "description": "Updated", "category": "", "active": True,
        }),
        "location_id": "loc1", "sheet_row_key": "Latte",
    }

    def _table(name):
        chain = MagicMock()
        if name == "menu_item_links":
            # Read link by external_id
            chain.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "link1", "platform": "square", "external_id": "SQ_OBJ_1",
                      "last_synced_hash": "old_hash",
                      "menu_items": canonical_item}
            )
            # Update link (set last_synced_hash)
            chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "menu_items":
            chain.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[canonical_item])
        elif name == "locations":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "loc1", "menu_sync_targets": ["square", "gbp"],
                      "gbp_account_id": "acct1"}
            )
        elif name == "clients":
            chain.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "c1", "gbp_access_token": "enc"}
            )
        elif name == "menu_sync_log":
            chain.insert.return_value.execute.return_value = MagicMock(data=[])
        return chain

    db.table.side_effect = _table

    gbp_pushed = False

    async def mock_push_gbp(loc, cli, mi, link):
        nonlocal gbp_pushed
        gbp_pushed = True
        return {"synced": True, "message": "Synced to GBP"}

    async def mock_push_square(loc, cli, mi, link):
        # This should NOT be called — Square is the source platform
        return {"synced": True, "message": "should not reach here"}

    with patch("jobs.menu_sync.get_db", return_value=db), \
         patch("jobs.menu_sync._push_to_gbp", new_callable=AsyncMock, side_effect=mock_push_gbp), \
         patch("jobs.menu_sync._push_to_square", new_callable=AsyncMock, side_effect=mock_push_square):
        result = await apply_square_inbound("c1", changed_objects)

    assert result["applied"] == 1
    assert gbp_pushed is True  # GBP was pushed (other target)
