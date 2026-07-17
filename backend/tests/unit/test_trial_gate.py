"""Tests for trial gate — blocks expired trials and enforces usage caps."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import pytz

AEST = pytz.timezone("Australia/Sydney")


@pytest.mark.asyncio
async def test_trial_gate_blocks_expired():
    """Expired trial is blocked with reason 'trial_expired'."""
    from middleware.trial_gate import check_trial_gate

    expired_client = {
        "trial_status": "expired",
        "trial_ends_at": (datetime.now(AEST) - timedelta(days=1)).isoformat(),
        "subscription_status": "trialing",
        "trial_usage": {"review_drafts": 5},
    }

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=expired_client
    )

    with patch("middleware.trial_gate.get_db", return_value=mock_db):
        result = await check_trial_gate("client-expired", "review_drafts")

    assert result["allowed"] is False
    assert result["reason"] == "trial_expired"


@pytest.mark.asyncio
async def test_trial_cap_enforced():
    """Trial usage at cap is blocked."""
    from middleware.trial_gate import check_trial_gate, TRIAL_CAPS

    cap = TRIAL_CAPS["review_drafts"]
    active_client = {
        "trial_status": "active",
        "trial_ends_at": (datetime.now(AEST) + timedelta(days=7)).isoformat(),
        "subscription_status": "trialing",
        "trial_usage": {"review_drafts": cap},
    }

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=active_client
    )

    with patch("middleware.trial_gate.get_db", return_value=mock_db):
        result = await check_trial_gate("client-at-cap", "review_drafts")

    assert result["allowed"] is False
    assert "trial_cap_reached" in result["reason"]
