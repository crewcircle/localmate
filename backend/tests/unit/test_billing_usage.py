"""Tests for GET /billing/usage (Phase 1) — used/cap/remaining visibility.

Caps are sourced from middleware.trial_gate.TRIAL_CAPS (single source of truth).
Active subs report unlimited; trial/expired report real caps; missing trial_usage
keys are 0; missing client -> 404; client_id is derived from auth (cross-tenant).
"""
import inspect
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytz
import pytest
from fastapi.params import Depends as DependsParam
from fastapi import HTTPException

from middleware.trial_gate import TRIAL_CAPS

AEST = pytz.timezone("Australia/Sydney")


def _clients_db(client_row):
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=client_row
    )
    return db


@pytest.mark.asyncio
async def test_usage_active_subscription_unlimited():
    from routers.billing import billing_usage

    client = {
        "trial_status": "converted",
        "trial_ends_at": (datetime.now(AEST) + timedelta(days=7)).isoformat(),
        "subscription_status": "active",
        "trial_usage": {"review_drafts": 250, "seo_reports": 9},
    }
    db = _clients_db(client)
    with patch("routers.billing.get_db", return_value=db):
        result = await billing_usage(client_id="client-active")

    assert result["subscription_status"] == "active"
    assert set(result["usage"]) == set(TRIAL_CAPS)
    for job_type in TRIAL_CAPS:
        entry = result["usage"][job_type]
        assert entry["cap"] is None
        assert entry["remaining"] is None
    # used is still the real count, even when unlimited
    assert result["usage"]["review_drafts"]["used"] == 250
    assert result["usage"]["seo_reports"]["used"] == 9


@pytest.mark.asyncio
async def test_usage_trial_within_cap():
    from routers.billing import billing_usage

    client = {
        "trial_status": "active",
        "trial_ends_at": (datetime.now(AEST) + timedelta(days=10)).isoformat(),
        "subscription_status": "trialing",
        # competitor_briefs + followup_messages intentionally absent -> 0 used
        "trial_usage": {"review_drafts": 10, "seo_reports": 1},
    }
    db = _clients_db(client)
    with patch("routers.billing.get_db", return_value=db):
        result = await billing_usage(client_id="client-trial")

    assert result["subscription_status"] == "trialing"
    u = result["usage"]
    assert u["review_drafts"] == {"used": 10, "cap": 100, "remaining": 90}
    assert u["seo_reports"] == {"used": 1, "cap": 2, "remaining": 1}
    # missing keys default to 0 used
    assert u["competitor_briefs"] == {"used": 0, "cap": 1, "remaining": 1}
    assert u["followup_messages"] == {"used": 0, "cap": 50, "remaining": 50}


@pytest.mark.asyncio
async def test_usage_trial_expired_still_reports_caps():
    """An expired trial still returns real caps (only active subs go unlimited)."""
    from routers.billing import billing_usage

    client = {
        "trial_status": "expired",
        "trial_ends_at": (datetime.now(AEST) - timedelta(days=2)).isoformat(),
        "subscription_status": "trial_expired",
        "trial_usage": {"review_drafts": 100},
    }
    db = _clients_db(client)
    with patch("routers.billing.get_db", return_value=db):
        result = await billing_usage(client_id="client-expired")

    assert result["trial_status"] == "expired"
    # caps are NOT null for expired (only active subs are unlimited)
    assert result["usage"]["review_drafts"] == {"used": 100, "cap": 100, "remaining": 0}
    assert result["usage"]["seo_reports"]["cap"] == 2
    assert result["usage"]["seo_reports"]["remaining"] == 2


@pytest.mark.asyncio
async def test_usage_missing_client_404():
    from routers.billing import billing_usage

    db = _clients_db(None)
    with patch("routers.billing.get_db", return_value=db):
        with pytest.raises(HTTPException) as exc_info:
            await billing_usage(client_id="client-missing")

    assert exc_info.value.status_code == 404


def test_usage_caps_sourced_from_trial_gate():
    """The endpoint must NOT duplicate caps — they come from TRIAL_CAPS."""
    assert set(TRIAL_CAPS) == {
        "review_drafts", "seo_reports", "competitor_briefs", "followup_messages"
    }
    assert TRIAL_CAPS == {
        "review_drafts": 100, "seo_reports": 2, "competitor_briefs": 1, "followup_messages": 50,
    }


def test_usage_client_id_derived_from_auth_not_request():
    """Cross-tenant protection (C8/D20): client_id is injected by the
    require_client_id auth dependency, never accepted from query/body."""
    from routers.billing import billing_usage
    from middleware.auth import require_client_id

    sig = inspect.signature(billing_usage)
    default = sig.parameters["client_id"].default
    assert isinstance(default, DependsParam), "client_id must be injected via Depends"
    assert default.dependency is require_client_id, (
        "client_id must be derived from require_client_id (tenant binding), "
        "not a query/body param"
    )
