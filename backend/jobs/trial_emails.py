"""Trial milestone emails — day1, day7, day13, and expired.

APScheduler-compatible async job. Runs hourly (wired via CronTrigger(hour=9)
in scheduler.py). Uses trial_emails_sent table for idempotency: one email
per (client_id, day_number) pair, ever.
"""

import logging
from datetime import datetime

import pytz

from db import get_db
from services.resend_email import (
    send_trial_day1_email,
    send_trial_day7_email,
    send_trial_day13_email,
    send_trial_expired_email,
)

AEST = pytz.timezone("Australia/Sydney")
logger = logging.getLogger(__name__)

# days_since_trial_start -> (send_fn, needs_client_id_arg).
# send_trial_expired_email differs: (to, business_name) only — handled separately.
_DAY_DISPATCH: dict[int, tuple] = {
    1:  (send_trial_day1_email, True),
    7:  (send_trial_day7_email, True),
    13: (send_trial_day13_email, True),
}


def _already_sent(db, client_id: str, day_number: int) -> bool:
    resp = (
        db.table("trial_emails_sent")
        .select("id")
        .eq("client_id", client_id)
        .eq("day_number", day_number)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def _record_send(db, client_id: str, day_number: int) -> None:
    db.table("trial_emails_sent").insert(
        {"client_id": client_id, "day_number": day_number}
    ).execute()


async def run_trial_emails() -> None:
    db = get_db()
    now = datetime.now(AEST)

    resp = (
        db.table("clients")
        .select("id, email, business_name, trial_started_at, trial_ends_at, trial_status")
        .eq("trial_status", "active")
        .execute()
    )
    clients = resp.data or []
    if not clients:
        logger.info("run_trial_emails: no active trial clients found")
        return

    processed = 0
    sent = 0

    for client in clients:
        processed += 1
        client_id = client["id"]

        try:
            raw_start = client.get("trial_started_at")
            if not raw_start:
                continue
            trial_start = datetime.fromisoformat(
                raw_start.replace("Z", "+00:00")
            ).astimezone(AEST)
            days_since = (now.date() - trial_start.date()).days

            if days_since in _DAY_DISPATCH:
                fn, _needs_id = _DAY_DISPATCH[days_since]
                if not _already_sent(db, client_id, days_since):
                    try:
                        await fn(client["email"], client["business_name"], client_id)
                        _record_send(db, client_id, days_since)
                        sent += 1
                        logger.info(
                            "Sent day-%d email to %s (%s)",
                            days_since, client["email"], client_id,
                        )
                    except Exception as exc:
                        logger.error(
                            "send_trial_day%d_email failed for %s: %s",
                            days_since, client_id, exc,
                        )

            raw_ends = client.get("trial_ends_at")
            if raw_ends:
                trial_ends = datetime.fromisoformat(
                    raw_ends.replace("Z", "+00:00")
                ).astimezone(AEST)
                if now > trial_ends and not _already_sent(db, client_id, -1):
                    try:
                        await send_trial_expired_email(
                            client["email"], client["business_name"]
                        )
                        _record_send(db, client_id, -1)
                        sent += 1
                        logger.info(
                            "Sent expired email to %s (%s)",
                            client["email"], client_id,
                        )
                    except Exception as exc:
                        logger.error(
                            "send_trial_expired_email failed for %s: %s",
                            client_id, exc,
                        )

        except Exception as exc:
            logger.error("trial_emails: unexpected error for client %s: %s", client_id, exc)

    logger.info("run_trial_emails: processed %d clients, sent %d emails", processed, sent)
