"""Tests for the mandatory webhook reconciliation job (Phase 0, C4)."""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


def _mock_db(rows, recovered_rows=None):
    """Mock supabase client.

    ``rows`` — pending rows returned by select().eq().lt().execute().
    ``recovered_rows`` — rows returned by the stale-processing recovery update
    (update().eq().lt().execute()).
    """
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=rows
    )
    db.table.return_value.update.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=recovered_rows or []
    )
    return db


@pytest.mark.asyncio
async def test_reconcile_reenqueues_stale_pending_rows():
    from utils import reconcile

    rows = [
        {"id": "e1", "provider": "stripe"},
        {"id": "e2", "provider": "gbp"},
        {"id": "e3", "provider": "menu"},
    ]
    db = _mock_db(rows)
    pool = MagicMock()
    pool.enqueue_job = AsyncMock(return_value=MagicMock())  # non-None → counted

    with patch("utils.reconcile.get_db", return_value=db):
        result = await reconcile.reconcile_pending_webhooks(pool)

    assert result["reenqueued"] == 3
    # deterministic _job_id passed so a duplicate enqueue is dropped by arq
    calls = pool.enqueue_job.call_args_list
    by_task = {c[0]: c[1].get("_job_id") for c in calls}
    assert ("process_stripe_event", "e1") in by_task
    assert by_task[("process_stripe_event", "e1")] == "process-webhook-e1"
    assert ("process_gbp_review", "e2") in by_task
    assert ("process_menu_update", "e3") in by_task


@pytest.mark.asyncio
async def test_reconcile_recovers_stale_processing_rows():
    from utils import reconcile

    # one row recovered from 'processing', then re-enqueued as pending
    db = _mock_db([{"id": "e1", "provider": "stripe"}], recovered_rows=[{"id": "e1"}])
    pool = MagicMock()
    pool.enqueue_job = AsyncMock(return_value=MagicMock())

    with patch("utils.reconcile.get_db", return_value=db):
        result = await reconcile.reconcile_pending_webhooks(pool)

    assert result["recovered"] == 1
    assert result["reenqueued"] == 1
    # the recovery update reset processing → pending AND cleared the lease
    upd_arg = db.table.return_value.update.call_args[0][0]
    assert upd_arg["status"] == "pending"
    assert upd_arg["processing_started_at"] is None
    db.table.return_value.update.return_value.eq.assert_called_with("status", "processing")


@pytest.mark.asyncio
async def test_reconcile_recovery_uses_processing_started_at_not_created_at():
    """Stale recovery must judge a 'processing' row by its lease start
    (processing_started_at), NOT created_at — otherwise a row that sat queued a
    long time then started processing could be reclaimed while actively running."""
    from utils import reconcile

    db = _mock_db([], recovered_rows=[])
    with patch("utils.reconcile.get_db", return_value=db):
        await reconcile.reconcile_pending_webhooks(MagicMock())

    # the recovery update filters processing rows by the lease column
    db.table.return_value.update.return_value.eq.return_value.lt.assert_called_once()
    lt_args = db.table.return_value.update.return_value.eq.return_value.lt.call_args[0]
    assert lt_args[0] == "processing_started_at"


@pytest.mark.asyncio
async def test_reconcile_noop_when_no_stale_rows():
    from utils import reconcile

    db = _mock_db([])
    with patch("utils.reconcile.get_db", return_value=db):
        result = await reconcile.reconcile_pending_webhooks(MagicMock())
    assert result["reenqueued"] == 0


@pytest.mark.asyncio
async def test_reconcile_skips_unknown_provider():
    from utils import reconcile

    db = _mock_db([{"id": "e1", "provider": "mystery"}])
    pool = MagicMock()
    pool.enqueue_job = AsyncMock()

    with patch("utils.reconcile.get_db", return_value=db):
        result = await reconcile.reconcile_pending_webhooks(pool)

    assert result["reenqueued"] == 0
    pool.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_creates_own_pool_when_none_given():
    from utils import reconcile

    db = _mock_db([{"id": "e1", "provider": "stripe"}])
    pool = MagicMock()
    pool.enqueue_job = AsyncMock(return_value=MagicMock())
    pool.close = AsyncMock()

    with patch("utils.reconcile.get_db", return_value=db), \
         patch("task_queue.get_arq_pool", new_callable=AsyncMock, return_value=pool):
        result = await reconcile.reconcile_pending_webhooks(None)

    assert result["reenqueued"] == 1
    pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_query_filters_pending_and_stale():
    from utils import reconcile

    db = _mock_db([])
    with patch("utils.reconcile.get_db", return_value=db):
        await reconcile.reconcile_pending_webhooks(MagicMock())

    # asserts the pending query chain used status='pending' and a created_at cutoff
    db.table.return_value.select.return_value.eq.assert_called_with("status", "pending")
    db.table.return_value.select.return_value.eq.return_value.lt.assert_called_once()
    lt_args = db.table.return_value.select.return_value.eq.return_value.lt.call_args[0]
    assert lt_args[0] == "created_at"
