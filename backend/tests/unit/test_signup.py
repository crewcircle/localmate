"""Tests for client signup endpoint."""
import pytest
from unittest.mock import patch, MagicMock
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
