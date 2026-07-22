"""Tests for client signup endpoint and GBP OAuth callback."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.exceptions import HTTPException


@pytest.mark.asyncio
async def test_signup_creates_client():
    """POST /auth/signup creates a client and returns client_id + trial end date."""
    from routers.auth import signup

    payload = {
        "business_name": "Sydney Dental Care",
        "business_type": "dental",
        "email": "info@sydneydentalcare.com.au",
        "suburb": "Bondi",
        "state": "NSW",
        "selected_jobs": ["review_drafts", "seo_reports"],
    }

    mock_customer = {"id": "cus_stub123"}

    # Chain: db.table("clients").select("id").eq("email", ...).execute() -> no existing
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq = MagicMock()
    mock_select.return_value = mock_select
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq

    mock_no_existing = MagicMock()
    mock_no_existing.data = []
    mock_eq.execute.return_value = mock_no_existing

    # Chain: db.table("clients").insert({...}).execute() -> new client
    mock_insert_resp = MagicMock()
    mock_insert_resp.data = [{"id": "client-new-456"}]
    mock_table.insert.return_value.execute.return_value = mock_insert_resp

    mock_db = MagicMock()
    mock_db.table.return_value = mock_table

    with patch("routers.auth.stripe.Customer.create", return_value=mock_customer), \
         patch("routers.auth.get_db", return_value=mock_db):
        result = await signup(payload)

    assert result["client_id"] == "client-new-456"
    assert "trial_ends_at" in result


@pytest.mark.asyncio
async def test_signup_rejects_duplicate_email():
    """POST /auth/signup returns 409 if email already exists."""
    from routers.auth import signup

    payload = {
        "business_name": "Bondi Beach Dental",
        "business_type": "dental",
        "email": "existing@example.com.au",
        "suburb": "Bondi",
        "state": "NSW",
        "selected_jobs": ["review_drafts"],
    }

    mock_customer = {"id": "cus_stub999"}

    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_eq = MagicMock()
    mock_select.return_value = mock_select
    mock_table.select.return_value = mock_select
    mock_select.eq.return_value = mock_eq

    mock_existing = MagicMock()
    mock_existing.data = [{"id": "client-existing"}]
    mock_eq.execute.return_value = mock_existing

    mock_db = MagicMock()
    mock_db.table.return_value = mock_table

    with patch("routers.auth.stripe.Customer.create", return_value=mock_customer), \
         patch("routers.auth.get_db", return_value=mock_db):
        with pytest.raises(HTTPException) as exc_info:
            await signup(payload)

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# GBP OAuth callback — resourceName parsing + provisioning enqueue (Phase 4, C4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gbp_callback_parses_resource_name_and_enqueues_provisioning():
    """gbp_callback parses account_id + location_id from resourceName, updates
    locations, and enqueues provisioning via arq (C4)."""
    from routers.auth import gbp_callback

    mock_db = MagicMock()

    def _table(name):
        chain = MagicMock()
        if name == "clients":
            chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "c1"}])
        elif name == "locations":
            # Default location exists → update it.
            chain.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "loc-1"}
            )
            chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "loc-1"}])
        return chain

    mock_db.table.side_effect = _table

    mock_request = MagicMock()
    mock_arq = MagicMock()
    mock_arq.enqueue_job = AsyncMock()
    mock_request.app.state.arq = mock_arq

    with patch("routers.auth.get_db", return_value=mock_db), \
         patch("routers.auth.exchange_code_for_tokens", new_callable=AsyncMock, return_value={
             "access_token": "tok",
             "refresh_token": "ref",
             "resourceName": "accounts/ACCT123/locations/LOC456",
         }), \
         patch("routers.auth.encrypt", side_effect=lambda x: f"enc_{x}"):
        result = await gbp_callback(
            request=mock_request,
            code="auth-code",
            state="c1",
        )

    assert result["status"] == "connected"
    # Provisioning was enqueued via arq.
    mock_arq.enqueue_job.assert_awaited_once_with("provision_gbp_notifications_task", "c1")
