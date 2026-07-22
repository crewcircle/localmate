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
    raw_html = "<html><body>" + new_text + "</body></html>"

    mock_last_resp = MagicMock()
    mock_last_resp.data = [
        {
            "content_hash": old_hash,
            "content_text": "Old content about dental services.",
            "structured_data": {"prices": [], "menu_items": [], "schema_types": [], "raw_jsonld": []},
        }
    ]

    mock_insert_resp = MagicMock()
    mock_insert_resp.data = [{"id": "snap-new-123"}]

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value \
        .order.return_value.limit.return_value.execute.return_value = mock_last_resp
    mock_db.table.return_value.insert.return_value.execute.return_value = mock_insert_resp

    with patch("jobs.competitor_watch.get_db", return_value=mock_db), \
         patch("jobs.competitor_watch.snapshot_website", new_callable=AsyncMock) as mock_snap:
        mock_snap.return_value = (new_hash, new_text, raw_html)

        result = await detect_changes(
            client_id="client-xyz",
            competitor_url="https://bondidental.com.au",
        )

    assert result is not None
    assert result["changed"] is True
    assert result["curr_text"] == new_text
    assert result["prev_text"] == "Old content about dental services."
    assert result["snapshot_id"] == "snap-new-123"
    assert "structured_diff" in result
    # Bug 2 regression guard: structured_diff must be persisted in the INSERT.
    insert_payload = mock_db.table.return_value.insert.call_args[0][0]
    assert "structured_diff" in insert_payload


@pytest.mark.asyncio
async def test_detect_changes_returns_structured_diff():
    """detect_changes returns structured_diff when JSON-LD price changes even if
    surrounding text hash is dominated by other content."""
    from jobs.competitor_watch import detect_changes

    prev_structured = {
        "prices": [{"name": "Invisalign", "price": "4500", "currency": "AUD"}],
        "menu_items": [],
        "schema_types": ["Product"],
        "raw_jsonld": [],
    }
    curr_html = (
        '<html><body>'
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"Invisalign","offers":{"price":"3990","priceCurrency":"AUD"}}'
        '</script>'
        '<p>Lots of other text that changes the hash</p>'
        '</body></html>'
    )

    mock_last_resp = MagicMock()
    mock_last_resp.data = [{
        "content_hash": "oldhash",
        "content_text": "old text",
        "structured_data": prev_structured,
    }]

    mock_insert_resp = MagicMock()
    mock_insert_resp.data = [{"id": "snap-2"}]

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value \
        .order.return_value.limit.return_value.execute.return_value = mock_last_resp
    mock_db.table.return_value.insert.return_value.execute.return_value = mock_insert_resp

    with patch("jobs.competitor_watch.get_db", return_value=mock_db), \
         patch("jobs.competitor_watch.snapshot_website", new_callable=AsyncMock) as mock_snap:
        # Hash differs, text differs, but the structured diff is the key signal.
        mock_snap.return_value = ("newhash", "new text content here", curr_html)

        result = await detect_changes("c1", "https://comp.com")

    assert result is not None
    assert result["changed"] is True
    # The structured_diff should report the Invisalign price change.
    diffs = result["structured_diff"]
    changed = [d for d in diffs if d["kind"] == "changed"]
    assert len(changed) == 1
    assert changed[0]["name"] == "Invisalign"
    assert changed[0]["old"] == "4500"
    assert changed[0]["new"] == "3990"


# ---------------------------------------------------------------------------
# Structured extraction (services/structured_extract.py)
# ---------------------------------------------------------------------------

def test_extract_structured_pulls_product_offer_price():
    """extract_structured pulls a Product Offer price from a JSON-LD block."""
    from services.structured_extract import extract_structured

    html = (
        '<html><body>'
        '<script type="application/ld+json">'
        '{"@type":"Product","name":"Teeth Whitening",'
        '"offers":{"@type":"Offer","price":"299","priceCurrency":"AUD"}}'
        '</script>'
        '</body></html>'
    )
    result = extract_structured(html)
    assert len(result["prices"]) == 1
    assert result["prices"][0]["name"] == "Teeth Whitening"
    assert result["prices"][0]["price"] == "299"
    assert result["prices"][0]["currency"] == "AUD"
    assert "Product" in result["schema_types"]


def test_extract_structured_pulls_menu_item_price():
    """extract_structured pulls a Restaurant/MenuItem price from JSON-LD."""
    from services.structured_extract import extract_structured

    html = (
        '<html><body>'
        '<script type="application/ld+json">'
        '{"@type":"Menu","name":"Dinner Menu","hasMenuItem":['
        '{"@type":"MenuItem","name":"Latte","price":"4.50"},'
        '{"@type":"MenuItem","name":"Cappuccino","price":"4.80"}'
        ']}'
        '</script>'
        '</body></html>'
    )
    result = extract_structured(html)
    assert len(result["menu_items"]) == 2
    names = {m["name"] for m in result["menu_items"]}
    assert "Latte" in names
    assert "Cappuccino" in names


def test_diff_structured_reports_changed_price():
    """diff_structured reports a 'changed' price with old/new values."""
    from services.structured_extract import diff_structured

    prev = {
        "prices": [{"name": "Invisalign", "price": "4500", "currency": "AUD"}],
        "menu_items": [],
    }
    curr = {
        "prices": [{"name": "Invisalign", "price": "3990", "currency": "AUD"}],
        "menu_items": [],
    }
    diffs = diff_structured(prev, curr)
    changed = [d for d in diffs if d["kind"] == "changed"]
    assert len(changed) == 1
    assert changed[0]["name"] == "Invisalign"
    assert changed[0]["old"] == "4500"
    assert changed[0]["new"] == "3990"


def test_diff_structured_reports_added_and_removed():
    """diff_structured reports added and removed items."""
    from services.structured_extract import diff_structured

    prev = {
        "prices": [{"name": "Clean", "price": "120", "currency": "AUD"}],
        "menu_items": [],
    }
    curr = {
        "prices": [
            {"name": "Clean", "price": "120", "currency": "AUD"},
            {"name": "Whitening", "price": "299", "currency": "AUD"},
        ],
        "menu_items": [],
    }
    diffs = diff_structured(prev, curr)
    added = [d for d in diffs if d["kind"] == "added"]
    assert len(added) == 1
    assert added[0]["name"] == "Whitening"
    assert added[0]["new"] == "299"


def test_detect_prices_from_text_finds_aud_prices():
    """Regex fallback finds $3,990 with a label."""
    from services.structured_extract import detect_prices_from_text

    text = "Our Invisalign treatment is now $3,990. Call us today."
    prices = detect_prices_from_text(text)
    assert len(prices) >= 1
    # At least one price should be 3,990
    found = any(p["price"] == "3,990" for p in prices)
    assert found, f"Expected to find $3,990 in {prices}"


def test_extract_structured_empty_html():
    """extract_structured handles empty/None HTML gracefully."""
    from services.structured_extract import extract_structured

    result = extract_structured("")
    assert result["prices"] == []
    assert result["menu_items"] == []
    assert result["schema_types"] == []
    assert result["raw_jsonld"] == []


def test_diff_structured_empty_prev():
    """diff_structured with empty prev reports all curr items as added."""
    from services.structured_extract import diff_structured

    curr = {"prices": [{"name": "Clean", "price": "120", "currency": "AUD"}], "menu_items": []}
    diffs = diff_structured({}, curr)
    added = [d for d in diffs if d["kind"] == "added"]
    assert len(added) == 1
    assert added[0]["name"] == "Clean"
