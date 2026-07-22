"""Tests for POST /billing/portal (Phase 1) — Stripe Billing Portal session.

Happy path returns a url; no stripe_customer_id -> 422; Stripe error -> 502;
missing client -> 404; client_id derived from auth (cross-tenant). The Stripe
param is `configuration` (not `configuration_id`) and is passed only when
STRIPE_PORTAL_CONFIG_ID is set.
"""
import inspect
from unittest.mock import patch, MagicMock

import pytest
from fastapi.params import Depends as DependsParam
from fastapi import HTTPException


def _clients_db(client_row):
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data=client_row
    )
    return db


def _settings_mock(*, portal_config_id="", dashboard_url="https://localmate.crewcircle.co"):
    s = MagicMock()
    s.stripe_portal_config_id = portal_config_id
    s.dashboard_url = dashboard_url
    return s


@pytest.mark.asyncio
async def test_portal_happy_path_returns_url():
    from routers.billing import billing_portal

    db = _clients_db({"stripe_customer_id": "cus_abc"})
    mock_session = MagicMock(url="https://billing.stripe.com/p/session_xyz")

    with patch("routers.billing.get_db", return_value=db), \
         patch("routers.billing.settings", _settings_mock(portal_config_id="")), \
         patch("routers.billing.stripe.billing_portal.Session.create", return_value=mock_session) as mock_create:
        result = await billing_portal(client_id="client-1")

    assert result["url"] == "https://billing.stripe.com/p/session_xyz"
    call = mock_create.call_args
    assert call[1]["customer"] == "cus_abc"
    assert call[1]["return_url"] == "https://localmate.crewcircle.co"
    # configuration omitted when STRIPE_PORTAL_CONFIG_ID is empty
    assert "configuration" not in call[1]


@pytest.mark.asyncio
async def test_portal_passes_configuration_when_configured():
    from routers.billing import billing_portal

    db = _clients_db({"stripe_customer_id": "cus_abc"})
    mock_session = MagicMock(url="https://billing.stripe.com/p/session_xyz")

    with patch("routers.billing.get_db", return_value=db), \
         patch("routers.billing.settings", _settings_mock(portal_config_id="bpc_123")), \
         patch("routers.billing.stripe.billing_portal.Session.create", return_value=mock_session) as mock_create:
        await billing_portal(client_id="client-1")

    call = mock_create.call_args
    # param is `configuration`, NOT `configuration_id`
    assert call[1]["configuration"] == "bpc_123"
    assert "configuration_id" not in call[1]


@pytest.mark.asyncio
async def test_portal_fallback_return_url_when_dashboard_url_empty():
    from routers.billing import billing_portal

    db = _clients_db({"stripe_customer_id": "cus_abc"})
    mock_session = MagicMock(url="https://billing.stripe.com/p/s")

    with patch("routers.billing.get_db", return_value=db), \
         patch("routers.billing.settings", _settings_mock(dashboard_url="")), \
         patch("routers.billing.stripe.billing_portal.Session.create", return_value=mock_session) as mock_create:
        await billing_portal(client_id="client-1")

    call = mock_create.call_args
    assert call[1]["return_url"] == "https://localmate.crewcircle.co/dashboard/settings"


@pytest.mark.asyncio
async def test_portal_no_customer_id_422():
    from routers.billing import billing_portal

    db = _clients_db({"stripe_customer_id": None})
    with patch("routers.billing.get_db", return_value=db), \
         patch("routers.billing.settings", _settings_mock()):
        with pytest.raises(HTTPException) as exc_info:
            await billing_portal(client_id="client-1")

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_portal_empty_customer_id_422():
    from routers.billing import billing_portal

    db = _clients_db({"stripe_customer_id": ""})
    with patch("routers.billing.get_db", return_value=db), \
         patch("routers.billing.settings", _settings_mock()):
        with pytest.raises(HTTPException) as exc_info:
            await billing_portal(client_id="client-1")

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_portal_stripe_error_502():
    from routers.billing import billing_portal

    db = _clients_db({"stripe_customer_id": "cus_abc"})
    with patch("routers.billing.get_db", return_value=db), \
         patch("routers.billing.settings", _settings_mock()), \
         patch("routers.billing.stripe.billing_portal.Session.create", side_effect=RuntimeError("stripe down")):
        with pytest.raises(HTTPException) as exc_info:
            await billing_portal(client_id="client-1")

    assert exc_info.value.status_code == 502
    assert "unavailable" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_portal_missing_client_404():
    from routers.billing import billing_portal

    db = _clients_db(None)
    with patch("routers.billing.get_db", return_value=db), \
         patch("routers.billing.settings", _settings_mock()):
        with pytest.raises(HTTPException) as exc_info:
            await billing_portal(client_id="client-missing")

    assert exc_info.value.status_code == 404


def test_portal_client_id_derived_from_auth_not_request():
    """Cross-tenant protection (C8/D20): client_id is injected by the
    require_client_id auth dependency, never accepted from query/body."""
    from routers.billing import billing_portal
    from middleware.auth import require_client_id

    sig = inspect.signature(billing_portal)
    default = sig.parameters["client_id"].default
    assert isinstance(default, DependsParam), "client_id must be injected via Depends"
    assert default.dependency is require_client_id, (
        "client_id must be derived from require_client_id (tenant binding), "
        "not a query/body param"
    )
