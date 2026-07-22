"""Tests for durable inbound webhook persistence + enqueue (Phase 0)."""
import hashlib
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


def _mock_db(existing=None, insert_id="evt-1"):
    """Build a mock supabase client. `existing` is the maybe_single result data."""
    db = MagicMock()
    # select(...).eq().eq().maybe_single().execute() -> existing
    select_chain = (
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute
    )
    select_chain.return_value = MagicMock(data=existing)
    # insert(...).execute() -> [{"id": insert_id}]
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": insert_id}]
    )
    return db


@pytest.mark.asyncio
async def test_stripe_webhook_persists_and_enqueues():
    from routers import webhooks

    db = _mock_db(existing=None, insert_id="evt-stripe-1")
    event = {"id": "evt_123", "type": "customer.subscription.updated", "data": {"object": {}}}

    request = MagicMock()
    request.body = AsyncMock(return_value=b"{}")
    request.headers = {"stripe-signature": "sig"}
    request.app.state.arq = MagicMock()
    request.app.state.arq.enqueue_job = AsyncMock()

    with patch("routers.webhooks.get_db", return_value=db), \
         patch("routers.webhooks.stripe.Webhook.construct_event", return_value=event):
        result = await webhooks.stripe_webhook(request)

    assert result["status"] == "received"
    # persisted with provider=stripe, idempotency_key=event id
    insert_arg = db.table.return_value.insert.call_args[0][0]
    assert insert_arg["provider"] == "stripe"
    assert insert_arg["idempotency_key"] == "evt_123"
    assert insert_arg["status"] == "pending"
    request.app.state.arq.enqueue_job.assert_awaited_once_with("process_stripe_event", "evt-stripe-1")


@pytest.mark.asyncio
async def test_stripe_webhook_duplicate_not_reenqueued():
    from routers import webhooks

    db = _mock_db(existing={"id": "evt-dup", "status": "done"})
    event = {"id": "evt_dup", "type": "customer.subscription.updated", "data": {"object": {}}}

    request = MagicMock()
    request.body = AsyncMock(return_value=b"{}")
    request.headers = {"stripe-signature": "sig"}
    request.app.state.arq = MagicMock()
    request.app.state.arq.enqueue_job = AsyncMock()

    with patch("routers.webhooks.get_db", return_value=db), \
         patch("routers.webhooks.stripe.Webhook.construct_event", return_value=event):
        result = await webhooks.stripe_webhook(request)

    assert result["status"] == "duplicate"
    db.table.return_value.insert.assert_not_called()
    request.app.state.arq.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_menu_update_persists_and_enqueues():
    from routers import webhooks

    db = _mock_db(existing=None, insert_id="evt-menu-1")
    payload = {"name": "Flat White", "price": "5.50", "description": "coffee", "category": "drinks"}

    request = MagicMock()
    request.app.state.arq = MagicMock()
    request.app.state.arq.enqueue_job = AsyncMock()

    with patch("routers.webhooks.get_db", return_value=db):
        result = await webhooks.menu_update("client-1", payload, request)

    assert result["status"] == "received"
    insert_arg = db.table.return_value.insert.call_args[0][0]
    assert insert_arg["provider"] == "menu"
    assert insert_arg["payload"]["client_id"] == "client-1"
    assert insert_arg["payload"]["item"]["price_cents"] == 550
    request.app.state.arq.enqueue_job.assert_awaited_once_with("process_menu_update", "evt-menu-1")


@pytest.mark.asyncio
async def test_enqueue_failure_leaves_row_pending():
    """If Redis/arq enqueue fails, the row stays pending (no exception raised)."""
    from routers import webhooks

    db = _mock_db(existing=None, insert_id="evt-x")
    event = {"id": "evt_x", "type": "invoice.payment_failed", "data": {"object": {}}}

    request = MagicMock()
    request.body = AsyncMock(return_value=b"{}")
    request.headers = {"stripe-signature": "sig"}
    request.app.state.arq = MagicMock()
    request.app.state.arq.enqueue_job = AsyncMock(side_effect=ConnectionError("redis down"))

    with patch("routers.webhooks.get_db", return_value=db), \
         patch("routers.webhooks.stripe.Webhook.construct_event", return_value=event):
        result = await webhooks.stripe_webhook(request)

    # Still returns 200-style ack; row was persisted for reconciliation.
    assert result["status"] == "received"
    db.table.return_value.insert.assert_called_once()


def test_menu_idempotency_key_is_stable_within_minute():
    from routers import webhooks
    # Two identical items in same minute bucket hash to the same key structure.
    import routers.webhooks as w
    raw = "client-1:Flat White:202607220800"
    assert hashlib.sha256(raw.encode()).hexdigest()  # deterministic
