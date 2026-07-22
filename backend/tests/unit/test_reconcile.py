"""Tests for the mandatory webhook reconciliation job (Phase 0, C4)."""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


def _mock_db(rows):
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
        data=rows
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
    pool.enqueue_job = AsyncMock()

    with patch("utils.reconcile.get_db", return_value=db):
        result = await reconcile.reconcile_pending_webhooks(pool)

    assert result["reenqueued"] == 3
    enqueued = [c[0] for c in pool.enqueue_job.call_args_list]
    assert ("process_stripe_event", "e1") in enqueued
    assert ("process_gbp_review", "e2") in enqueued
    assert ("process_menu_update", "e3") in enqueued


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
    pool.enqueue_job = AsyncMock()
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

    # asserts the query chain used status='pending' and a created_at cutoff
    db.table.return_value.select.return_value.eq.assert_called_with("status", "pending")
    db.table.return_value.select.return_value.eq.return_value.lt.assert_called_once()
    lt_args = db.table.return_value.select.return_value.eq.return_value.lt.call_args[0]
    assert lt_args[0] == "created_at"
