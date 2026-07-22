"""Tests that trial milestone emails enqueue durable arq jobs (C4 outbound migration).

run_trial_emails now enqueues `send_email_task` arq jobs (the Phase 0 durable
Resend wrapper) instead of calling the Resend senders directly, so a transport
failure retries + dead-letters rather than being silently swallowed.
"""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytz
import pytest

AEST = pytz.timezone("Australia/Sydney")


def _trial_emails_db(clients):
    """Mock supabase routing .table('clients') and .table('trial_emails_sent')
    to separate chain mocks (a single shared chain cannot serve both)."""
    db = MagicMock()

    clients_table = MagicMock()
    clients_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=clients)

    sent_table = MagicMock()
    # _already_sent: select('id').eq('client_id').eq('day_number').limit(1).execute() -> []
    sent_table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    sent_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "row-1"}])

    db.table.side_effect = lambda name: clients_table if name == "clients" else sent_table
    return db, sent_table


@pytest.mark.asyncio
async def test_day_email_enqueues_send_email_task():
    from jobs.trial_emails import run_trial_emails

    now = datetime.now(AEST)
    client = {
        "id": "c1",
        "email": "owner@biz1.com.au",
        "business_name": "Biz One",
        "trial_started_at": (now - timedelta(days=1)).isoformat(),  # days_since == 1
        "trial_ends_at": (now + timedelta(days=13)).isoformat(),    # not expired
        "trial_status": "active",
    }
    db, sent_table = _trial_emails_db([client])

    pool = MagicMock()
    pool.enqueue_job = AsyncMock()

    with patch("jobs.trial_emails.get_db", return_value=db):
        await run_trial_emails(pool)

    # Enqueued a durable send_email_task for the day-1 email, with the right kind
    # and positional args (kind, to, business_name, client_id).
    pool.enqueue_job.assert_any_call(
        "send_email_task", "trial_day1", "owner@biz1.com.au", "Biz One", "c1"
    )
    # Idempotency row recorded after successful enqueue.
    sent_table.insert.assert_called()


@pytest.mark.asyncio
async def test_expired_email_enqueues_send_email_task():
    from jobs.trial_emails import run_trial_emails

    now = datetime.now(AEST)
    client = {
        "id": "c2",
        "email": "owner@biz2.com.au",
        "business_name": "Biz Two",
        "trial_started_at": (now - timedelta(days=20)).isoformat(),  # not a milestone day
        "trial_ends_at": (now - timedelta(days=6)).isoformat(),      # expired
        "trial_status": "active",
    }
    db, sent_table = _trial_emails_db([client])

    pool = MagicMock()
    pool.enqueue_job = AsyncMock()

    with patch("jobs.trial_emails.get_db", return_value=db):
        await run_trial_emails(pool)

    # Expired email enqueued (kind, to, business_name) — no client_id arg.
    pool.enqueue_job.assert_any_call(
        "send_email_task", "trial_expired", "owner@biz2.com.au", "Biz Two"
    )
    sent_table.insert.assert_called()


@pytest.mark.asyncio
async def test_does_not_directly_call_resend_senders():
    """The Resend senders must no longer be called inline — sends go via arq."""
    from jobs.trial_emails import run_trial_emails

    now = datetime.now(AEST)
    client = {
        "id": "c1",
        "email": "owner@biz1.com.au",
        "business_name": "Biz One",
        "trial_started_at": (now - timedelta(days=1)).isoformat(),
        "trial_ends_at": (now + timedelta(days=13)).isoformat(),
        "trial_status": "active",
    }
    db, _ = _trial_emails_db([client])
    pool = MagicMock()
    pool.enqueue_job = AsyncMock()

    with patch("jobs.trial_emails.get_db", return_value=db), \
         patch("services.resend_email.send_email_strict", new_callable=AsyncMock) as mock_strict, \
         patch("services.resend_email.send_trial_day1_email", new_callable=AsyncMock) as mock_day1:
        await run_trial_emails(pool)

    mock_strict.assert_not_awaited()
    mock_day1.assert_not_awaited()
    pool.enqueue_job.assert_awaited()


@pytest.mark.asyncio
async def test_idempotent_already_sent_not_reenqueued():
    """A milestone already recorded in trial_emails_sent is not re-enqueued."""
    from jobs.trial_emails import run_trial_emails

    now = datetime.now(AEST)
    client = {
        "id": "c1",
        "email": "owner@biz1.com.au",
        "business_name": "Biz One",
        "trial_started_at": (now - timedelta(days=1)).isoformat(),
        "trial_ends_at": (now + timedelta(days=13)).isoformat(),
        "trial_status": "active",
    }
    db = MagicMock()
    clients_table = MagicMock()
    clients_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[client])
    sent_table = MagicMock()
    # _already_sent returns a row -> already sent
    sent_table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "existing"}]
    )
    db.table.side_effect = lambda name: clients_table if name == "clients" else sent_table

    pool = MagicMock()
    pool.enqueue_job = AsyncMock()

    with patch("jobs.trial_emails.get_db", return_value=db):
        await run_trial_emails(pool)

    pool.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_pool_skips_safely():
    """Without an arq pool the run skips rather than crashing."""
    from jobs.trial_emails import run_trial_emails

    db = MagicMock()
    with patch("jobs.trial_emails.get_db", return_value=db):
        await run_trial_emails(None)  # must not raise


@pytest.mark.asyncio
async def test_enqueue_failure_day_rolls_back_idempotency_record():
    """An enqueue failure must roll back the tentatively-recorded idempotency
    row so the next run can retry — never leaving a row that blocks future sends
    (which would silently drop the email)."""
    from jobs.trial_emails import run_trial_emails

    now = datetime.now(AEST)
    client = {
        "id": "c1",
        "email": "owner@biz1.com.au",
        "business_name": "Biz One",
        "trial_started_at": (now - timedelta(days=1)).isoformat(),  # days_since == 1
        "trial_ends_at": (now + timedelta(days=13)).isoformat(),    # not expired
        "trial_status": "active",
    }
    db, sent_table = _trial_emails_db([client])

    pool = MagicMock()
    pool.enqueue_job = AsyncMock(side_effect=RuntimeError("redis down"))

    with patch("jobs.trial_emails.get_db", return_value=db):
        await run_trial_emails(pool)  # per-client handler swallows; run completes

    pool.enqueue_job.assert_awaited()
    # The idempotency row was tentatively recorded...
    sent_table.insert.assert_called()
    # ...then rolled back (delete targeting this client + day) so it does not
    # block the next run.
    sent_table.delete.assert_called_once()
    sent_table.delete.return_value.eq.assert_called_with("client_id", "c1")
    sent_table.delete.return_value.eq.return_value.eq.assert_called_with("day_number", 1)


@pytest.mark.asyncio
async def test_enqueue_failure_expired_rolls_back_idempotency_record():
    """Same rollback guarantee for the expired-email loop (day_number -1)."""
    from jobs.trial_emails import run_trial_emails

    now = datetime.now(AEST)
    client = {
        "id": "c2",
        "email": "owner@biz2.com.au",
        "business_name": "Biz Two",
        "trial_started_at": (now - timedelta(days=20)).isoformat(),  # not a milestone day
        "trial_ends_at": (now - timedelta(days=6)).isoformat(),      # expired
        "trial_status": "active",
    }
    db, sent_table = _trial_emails_db([client])

    pool = MagicMock()
    pool.enqueue_job = AsyncMock(side_effect=RuntimeError("redis down"))

    with patch("jobs.trial_emails.get_db", return_value=db):
        await run_trial_emails(pool)

    pool.enqueue_job.assert_awaited()
    sent_table.insert.assert_called()
    sent_table.delete.assert_called_once()
    sent_table.delete.return_value.eq.assert_called_with("client_id", "c2")
    sent_table.delete.return_value.eq.return_value.eq.assert_called_with("day_number", -1)
