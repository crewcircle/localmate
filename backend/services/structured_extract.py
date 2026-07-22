"""Structured data extraction from competitor HTML (JSON-LD / schema.org).

Pure-parse module — no network calls. Feeds off HTML already fetched by
``snapshot_website`` in ``jobs/competitor_watch.py``.

Functions:
  - ``extract_structured(html)`` — parse JSON-LD blocks, extract Product/Offer
    prices and Restaurant/Menu/MenuItem items.
  - ``detect_prices_from_text(clean_text)`` — regex fallback for AUD ``$``
    price patterns with nearby label capture.
  - ``diff_structured(prev, curr)`` — field-level diffs (added/removed/changed).
"""
import json
import logging
import re

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON-LD parsing helpers
# ---------------------------------------------------------------------------

def _flatten_jsonld(obj):
    """Yield individual JSON-LD objects, flattening ``@graph`` arrays."""
    if isinstance(obj, list):
        for item in obj:
            yield from _flatten_jsonld(item)
    elif isinstance(obj, dict):
        graph = obj.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _flatten_jsonld(item)
        else:
            yield obj


def _schema_type(obj: dict) -> str:
    """Return the primary @type of a JSON-LD object (first if list)."""
    t = obj.get("@type", "")
    if isinstance(t, list):
        return t[0] if t else ""
    return t or ""


def _extract_price(obj: dict) -> tuple[str | None, str | None]:
    """Extract (price, currency) from an Offer or Product-like object."""
    price = None
    currency = None

    if "price" in obj:
        price = str(obj["price"])
    elif "priceSpecification" in obj and isinstance(obj["priceSpecification"], dict):
        ps = obj["priceSpecification"]
        if "price" in ps:
            price = str(ps["price"])
        if "priceCurrency" in ps:
            currency = ps["priceCurrency"]

    if "priceCurrency" in obj:
        currency = obj["priceCurrency"]

    return price, currency


def extract_structured(html: str) -> dict:
    """Parse JSON-LD blocks from HTML and extract structured price/menu data.

    Returns ``{prices: [{name, price, currency}], menu_items: [{name, price}],
    schema_types: [...], raw_jsonld: [...]}``. Never raises — malformed JSON-LD
    is skipped silently.
    """
    if not html:
        return {"prices": [], "menu_items": [], "schema_types": [], "raw_jsonld": []}

    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", {"type": "application/ld+json"})

    prices: list[dict] = []
    menu_items: list[dict] = []
    schema_types: list[str] = []
    raw_jsonld: list = []

    for script in scripts:
        text = script.string or script.get_text() or ""
        if not text.strip():
            continue
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        raw_jsonld.append(data)

        for obj in _flatten_jsonld(data):
            if not isinstance(obj, dict):
                continue
            stype = _schema_type(obj)
            if stype:
                schema_types.append(stype)

            # Product with offers
            if stype == "Product":
                name = obj.get("name", "")
                offers = obj.get("offers", [])
                if isinstance(offers, dict):
                    offers = [offers]
                for offer in offers:
                    if not isinstance(offer, dict):
                        continue
                    price, currency = _extract_price(offer)
                    if price:
                        prices.append(
                            {"name": name, "price": price, "currency": currency or "AUD"}
                        )

            # Offer directly
            elif stype == "Offer":
                price, currency = _extract_price(obj)
                if price:
                    prices.append(
                        {"name": obj.get("name", ""), "price": price, "currency": currency or "AUD"}
                    )

            # MenuItem
            if stype == "MenuItem":
                name = obj.get("name", "")
                price, _ = _extract_price(obj)
                if price:
                    menu_items.append({"name": name, "price": price})

            # Menu with hasMenuItem
            if stype == "Menu":
                for item in obj.get("hasMenuItem", []):
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name", "")
                    price, _ = _extract_price(item)
                    if price:
                        menu_items.append({"name": name, "price": price})

    return {
        "prices": prices,
        "menu_items": menu_items,
        "schema_types": sorted(set(schema_types)),
        "raw_jsonld": raw_jsonld,
    }


# ---------------------------------------------------------------------------
# Regex fallback
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9\s\-/']{2,40}?)\s*\$\s*(\d[\d,]*(?:\.\d{2})?)"
)


def detect_prices_from_text(clean_text: str) -> list[dict]:
    """Regex fallback for AUD ``$`` price patterns with nearby label capture.

    Returns ``[{name, price, currency}]``. Useful for sites with no JSON-LD.
    """
    if not clean_text:
        return []
    results = []
    for match in _PRICE_RE.finditer(clean_text):
        label = match.group(1).strip()
        price = match.group(2).strip()
        results.append({"name": label, "price": price, "currency": "AUD"})
    return results


# ---------------------------------------------------------------------------
# Diffing
# ---------------------------------------------------------------------------

def _diff_keyed(prev: dict, curr: dict, field: str) -> list[dict]:
    """Diff a list of {name, price} dicts keyed by name."""
    prev_map = {item["name"]: item["price"] for item in prev.get(field, []) if item.get("name")}
    curr_map = {item["name"]: item["price"] for item in curr.get(field, []) if item.get("name")}

    diffs: list[dict] = []
    for name, price in curr_map.items():
        if name not in prev_map:
            diffs.append({"kind": "added", "name": name, "old": None, "new": price})
        elif prev_map[name] != price:
            diffs.append({"kind": "changed", "name": name, "old": prev_map[name], "new": price})
    for name, price in prev_map.items():
        if name not in curr_map:
            diffs.append({"kind": "removed", "name": name, "old": price, "new": None})
    return diffs


def diff_structured(prev: dict, curr: dict) -> list[dict]:
    """Field-level diffs between two ``extract_structured`` results.

    Returns a list of ``{kind, name, old, new}`` where ``kind`` is
    ``'added'``, ``'removed'``, or ``'changed'``. Compares both ``prices`` and
    ``menu_items`` fields.
    """
    if not prev:
        prev = {}
    if not curr:
        curr = {}
    return _diff_keyed(prev, curr, "prices") + _diff_keyed(prev, curr, "menu_items")
