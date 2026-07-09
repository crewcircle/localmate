import hashlib
import logging
import re

import httpx
from bs4 import BeautifulSoup

from db import get_db
from services.claude import generate_competitor_brief

logger = logging.getLogger(__name__)


async def snapshot_website(url: str) -> tuple[str, str]:
    """Fetch a competitor URL, strip non-content elements, and return (md5_hash, clean_text).

    Returns ("", "") on any failure.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; LocalBizBot/1.0)"},
                follow_redirects=True,
                timeout=15,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            clean_text = " ".join(soup.get_text().split())
            md5_hex = hashlib.md5(clean_text.encode()).hexdigest()
            return md5_hex, clean_text
    except Exception as e:
        logger.error(f"snapshot_website failed for {url}: {e}")
        return "", ""


async def detect_changes(client_id: str, competitor_url: str) -> dict | None:
    """Compare the latest snapshot hash against a fresh fetch.

    Returns None when the content is unchanged or the fetch failed.
    Returns a dict with change details on difference, including the new snapshot row id.

    The caller is responsible for calling ``run_competitor_snapshots_all_clients``
    which invokes this per client/URL pair.
    """
    db = get_db()

    last_resp = (
        db.table("competitor_snapshots")
        .select("content_hash, content_text")
        .eq("client_id", client_id)
        .eq("competitor_url", competitor_url)
        .order("captured_at", desc=True)
        .limit(1)
        .execute()
    )

    new_hash, new_text = await snapshot_website(competitor_url)
    if not new_hash:
        return None

    last_text = ""
    if last_resp.data:
        last_row = last_resp.data[0]
        if last_row["content_hash"] == new_hash:
            return None
        last_text = last_row.get("content_text") or ""

    insert_resp = (
        db.table("competitor_snapshots")
        .insert({
            "client_id": client_id,
            "competitor_url": competitor_url,
            "content_hash": new_hash,
            "content_text": new_text,
        })
        .execute()
    )

    new_id = insert_resp.data[0]["id"] if insert_resp.data else None

    return {
        "changed": True,
        "prev_text": last_text,
        "curr_text": new_text,
        "snapshot_id": new_id,
    }


def _parse_threat_level(brief: str) -> str:
    """Extract threat level (LOW | MEDIUM | HIGH) from a Claude-generated brief."""
    match = re.search(r"(?i)threat\s*level[:\s]*(LOW|MEDIUM|HIGH)", brief)
    if match:
        return match.group(1).upper()
    return "MEDIUM"


async def run_competitor_snapshots_all_clients() -> None:
    """APScheduler job — runs Sunday 10pm AEST.

    For every client with ``'competitor_watch'`` in ``active_jobs``:

    1. Snapshot each URL listed in ``competitor_urls``.
    2. If changes are detected, collect them into a list.
    3. Call ``generate_competitor_brief`` once per changed client.
    4. Persist the brief text and extracted threat level on each new snapshot row.

    Each client is wrapped in its own try/except so one failure never crashes
    the entire job run.
    """
    db = get_db()

    resp = (
        db.table("clients")
        .select("id, business_name, competitor_urls, active_jobs")
        .execute()
    )

    if not resp.data:
        logger.info("No clients found — skipping competitor watch")
        return

    clients = [
        c for c in resp.data
        if "competitor_watch" in (c.get("active_jobs") or [])
        and c.get("competitor_urls")
    ]

    if not clients:
        logger.info("No clients with competitor_watch enabled — skipping")
        return

    for client in clients:
        client_id = client["id"]
        business_name = client["business_name"]
        competitor_urls = client["competitor_urls"]

        try:
            changes = []
            for url in competitor_urls:
                result = await detect_changes(client_id, url)
                if result is not None:
                    changes.append({"url": url, **result})

            if not changes:
                logger.info(f"No competitor changes detected for {business_name}")
                continue

            parts = []
            for c in changes:
                parts.append(
                    f"Competitor: {c['url']}\n"
                    f"Previous snippet: {c['prev_text'][:300]}\n"
                    f"Current snippet:  {c['curr_text'][:300]}"
                )
            changes_summary = "\n\n".join(parts)

            brief = await generate_competitor_brief(business_name, changes_summary)
            threat_level = _parse_threat_level(brief)

            for c in changes:
                sid = c.get("snapshot_id")
                if sid:
                    db.table("competitor_snapshots").update({
                        "brief_text": brief,
                        "threat_level": threat_level,
                    }).eq("id", sid).execute()

            logger.info(
                f"Competitor brief generated for {business_name} "
                f"({len(changes)} change(s), threat: {threat_level})"
            )

        except Exception as e:
            logger.error(
                f"Competitor watch failed for client {client_id} "
                f"({business_name}): {e}"
            )
