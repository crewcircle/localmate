import logging
from datetime import datetime, timedelta

import pytz

from config import settings
from db import get_db
from services.dataforseo import get_local_rankings
from services.claude import generate_seo_report

logger = logging.getLogger(__name__)

AEST = pytz.timezone("Australia/Sydney")


def _monday_of_week(dt: datetime) -> datetime:
    """Return Monday 00:00 AEST of the week containing *dt*."""
    return (dt - timedelta(days=dt.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


async def send_seo_email(client: dict, report_text: str) -> None:
    """Send the SEO report email to a client via Resend."""
    from services.resend_email import _get_resend

    business_name = client.get("business_name", "Your Business")
    email = client.get("email")
    if not email:
        logger.warning("No email for client %s — skipping SEO email", client.get("id"))
        return

    try:
        r = _get_resend()
        r.Emails.send(
            from_email=f"hello@{settings.base_domain}",
            to_email=email,
            subject=f"Weekly SEO Report — {business_name}",
            html=f"<p>Hi {business_name} team,</p><p>Here is your weekly SEO ranking report:</p><pre style='font-family: sans-serif; white-space: pre-wrap;'>{report_text}</pre>",
        )
        logger.info("SEO report email sent to %s (%s)", business_name, email)
    except Exception as e:
        logger.error("send_seo_email failed for %s: %s", client.get("id"), e)


def _fetch_rankings(db, client_id: str, week_start: datetime) -> list[dict]:
    """Fetch stored rankings for a client for a given week."""
    resp = (
        db.table("rankings")
        .select("keyword, position, url")
        .eq("client_id", client_id)
        .eq("week_start", week_start.isoformat())
        .execute()
    )
    return resp.data if resp.data else []


async def run_seo_rankings_all_clients() -> None:
    """APScheduler job — Monday 6am AEST.

    For every client with ``'seo_report'`` in ``active_jobs``:
      1. Fetch live rankings for each tracked keyword.
      2. Upsert results into the ``rankings`` table.
      3. Build this-week and last-week snapshots.
      4. Generate a plain-English report via Claude.
      5. Email the report to the client.

    Each client is wrapped in its own try/except — a single client failure
    never crashes the scheduler.
    """
    db = get_db()
    now = datetime.now(AEST)
    week_start = _monday_of_week(now)
    last_week_start = week_start - timedelta(days=7)

    # Fetch clients with SEO monitoring enabled
    try:
        resp = (
            db.table("clients")
            .select("id, business_name, email, suburb, state, keywords")
            .contains("active_jobs", ["seo_report"])
            .execute()
        )
        clients = resp.data or []
    except Exception as e:
        logger.error("Failed to fetch clients for SEO report: %s", e)
        return

    if not clients:
        logger.info("No clients with seo_report job found")
        return

    for client in clients:
        client_id = client["id"]
        keywords: list[str] = client.get("keywords") or []
        if not keywords:
            logger.info("Client %s has no keywords — skipping", client_id)
            continue

        location = f"{client.get('suburb', '')} {client.get('state', '')}".strip()

        try:
            for kw in keywords:
                result = await get_local_rankings(
                    keyword=kw,
                    location=location,
                    client_suburb=client.get("suburb", ""),
                )
                upsert_payload = {
                    "client_id": client_id,
                    "keyword": kw,
                    "location": location or "Australia",
                    "position": result.get("position"),
                    "url": result.get("url"),
                    "week_start": week_start.isoformat(),
                    "captured_at": now.isoformat(),
                }
                try:
                    db.table("rankings").upsert(
                        upsert_payload,
                        on_conflict=["client_id", "keyword", "week_start"],
                    ).execute()
                except Exception as e:
                    logger.error(
                        "Failed to upsert ranking for %s / '%s': %s",
                        client_id,
                        kw,
                        e,
                    )
        except Exception as e:
            logger.error(
                "SEO rankings fetch failed for client %s: %s", client_id, e
            )
            continue

        # Build this-week / last-week snapshots for the report
        try:
            this_week = _fetch_rankings(db, client_id, week_start)
            last_week = _fetch_rankings(db, client_id, last_week_start)
        except Exception as e:
            logger.error(
                "Failed to fetch stored rankings for %s: %s", client_id, e
            )
            continue

        # Generate and send the report
        try:
            report_text = await generate_seo_report(
                business_name=client.get("business_name", ""),
                this_week=this_week,
                last_week=last_week,
            )
        except Exception as e:
            logger.error(
                "Failed to generate SEO report for %s: %s", client_id, e
            )
            continue

        await send_seo_email(client, report_text)
