"""Trial milestone emails — day1, day7, day13, and expired.

APScheduler-compatible async job. Runs daily (wired via CronTrigger(hour=9) in
scheduler.py, which enqueues the ``run_trial_emails_daily`` arq task). Uses the
``trial_emails_sent`` table for idempotency: one email per (client_id,
day_number) pair, ever.

Outbound sends are durable (C4): instead of calling the Resend senders directly,
this job enqueues a ``send_email_task`` arq job (the Phase 0 durable wrapper) so
a Resend transport failure retries with backoff and dead-letters on exhaustion
rather than being silently swallowed. The idempotency row is recorded BEFORE the
enqueue and rolled back if the enqueue fails, so a failed enqueue can never leave
a row that would block a future send (which would cause a silent drop); a
permanently-failed send lands in ``dead_letter`` for operator replay.
"""

import logging
from datetime import datetime

import pytz

from db import get_db

AEST = pytz.timezone("Australia/Sydney")
logger = logging.getLogger(__name__)

# days_since_trial_start -> Resend email kind (see services.resend_email._content).
# The expired email differs (no client_id arg) and is handled separately.
_DAY_KIND: dict[int, str] = {
    1:  "trial_day1",
    7:  "trial_day7",
    13: "trial_day13",
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


def _unrecord_send(db, client_id: str, day_number: int) -> None:
    """Remove a tentatively-recorded idempotency row (enqueue-failure rollback)."""
    (
        db.table("trial_emails_sent")
        .delete()
        .eq("client_id", client_id)
        .eq("day_number", day_number)
        .execute()
    )


async def run_trial_emails(pool) -> None:
    """Enqueue durable trial-milestone emails for all active-trial clients.

    ``pool`` is the arq Redis pool (``ctx["redis"]`` from the
    ``run_trial_emails_daily`` cron task). When absent the run is skipped — the
    next run with a live pool picks it up.
    """
    if pool is None:
        logger.warning("run_trial_emails: no arq pool available — skipping this run")
        return

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

            if days_since in _DAY_KIND:
                if not _already_sent(db, client_id, days_since):
                    # Record the idempotency row FIRST so a crash between
                    # enqueue-success and record does not cause a duplicate
                    # delivery on the next run. If the enqueue fails, roll the
                    # row back so the next run can retry (no silent drop).
                    _record_send(db, client_id, days_since)
                    try:
                        await pool.enqueue_job(
                            "send_email_task",
                            _DAY_KIND[days_since],
                            client["email"],
                            client["business_name"],
                            client_id,
                        )
                        sent += 1
                        logger.info(
                            "Enqueued day-%d email to %s (%s)",
                            days_since, client["email"], client_id,
                        )
                    except Exception:
                        _unrecord_send(db, client_id, days_since)
                        raise

            raw_ends = client.get("trial_ends_at")
            if raw_ends:
                trial_ends = datetime.fromisoformat(
                    raw_ends.replace("Z", "+00:00")
                ).astimezone(AEST)
                if now > trial_ends and not _already_sent(db, client_id, -1):
                    # Record-first / rollback-on-enqueue-failure (see above).
                    _record_send(db, client_id, -1)
                    try:
                        await pool.enqueue_job(
                            "send_email_task",
                            "trial_expired",
                            client["email"],
                            client["business_name"],
                        )
                        sent += 1
                        logger.info(
                            "Enqueued expired email to %s (%s)",
                            client["email"], client_id,
                        )
                    except Exception:
                        _unrecord_send(db, client_id, -1)
                        raise

        except Exception as exc:
            logger.error("trial_emails: unexpected error for client %s: %s", client_id, exc)

    logger.info("run_trial_emails: processed %d clients, enqueued %d emails", processed, sent)
