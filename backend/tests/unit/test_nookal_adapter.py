"""Tests for the Nookal booking adapter (mocked httpx — no live API calls)."""
import pytest
from unittest.mock import patch

import httpx

from services import nookal


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=httpx.Request("GET", "x"), response=httpx.Response(self.status_code)
            )


class _FakeClient:
    """Minimal async context-manager httpx stand-in returning canned GET responses."""

    def __init__(self, responses):
        # responses: a single _FakeResp, a list (sequential), or an Exception to raise.
        self._responses = responses if isinstance(responses, list) else [responses]
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kw):
        self.calls.append((url, kw))
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


_NOOKAL_PAYLOAD = {
    "data": {
        "appointments": [
            {
                "patientId": "p-100",
                "patientName": "Alice Wong",
                "patientPhone": "+61400000001",
                "patientEmail": "alice@example.com",
                "appointmentType": "Physio Consult",
                "date": "2026-05-20T09:00:00+10:00",
                "status": "Completed",
                "practitionerId": "prac-7",
                "practitionerName": "Dr Patel",
                "billing": {"type": "gap", "fund": "HCF", "gap_amount": 40.0},
            }
        ]
    }
}


def test_nookal_metadata():
    assert nookal.ADAPTER_NAME == "nookal"
    assert nookal.ID_COLUMN == "nookal_id"
    assert nookal.CREDENTIAL_KEYS == ["nookal_api_key"]
    assert nookal.SUPPORTS_REBOOK is True
    assert nookal.AUTH_MODEL == "api_key"


@pytest.mark.asyncio
async def test_get_appointments_maps_to_canonical():
    client = {"id": "c1", "nookal_api_key": "nk-key"}
    fake = _FakeClient(_FakeResp(_NOOKAL_PAYLOAD))
    with patch("services.nookal.httpx.AsyncClient", return_value=fake):
        result = await nookal.get_appointments(client, "2026-05-01", "2026-05-31", "completed")

    assert len(result) == 1
    appt = result[0]
    assert appt["patient_id"] == "p-100"
    assert appt["patient_name"] == "Alice Wong"
    assert appt["patient_phone"] == "+61400000001"
    assert appt["treatment_type"] == "Physio Consult"
    assert appt["appointment_date"] == "2026-05-20"
    assert appt["practitioner_id"] == "prac-7"
    assert appt["practitioner_name"] == "Dr Patel"
    assert appt["claim"] == {"type": "gap", "fund": "HCF", "gap_amount": 40.0}

    # api_key sent as a query param on the getAppointments endpoint.
    url, kw = fake.calls[0]
    assert url.endswith("/getAppointments")
    assert kw["params"]["api_key"] == "nk-key"
    assert kw["params"]["from"] == "2026-05-01"
    assert kw["params"]["to"] == "2026-05-31"


@pytest.mark.asyncio
async def test_get_appointments_http_error_returns_empty():
    client = {"id": "c1", "nookal_api_key": "nk-key"}
    fake = _FakeClient(httpx.ConnectError("boom"))
    with patch("services.nookal.httpx.AsyncClient", return_value=fake):
        result = await nookal.get_appointments(client, "2026-05-01", "2026-05-31")
    assert result == []


@pytest.mark.asyncio
async def test_get_appointments_no_api_key_returns_empty():
    # No per-client key and no global fallback.
    client = {"id": "c1"}
    with patch("services.nookal.httpx.AsyncClient") as mock_client:
        result = await nookal.get_appointments(client, "2026-05-01", "2026-05-31")
    assert result == []
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_get_future_appointments_returns_items():
    client = {"id": "c1", "nookal_api_key": "nk-key"}
    fake = _FakeClient(_FakeResp(_NOOKAL_PAYLOAD))
    with patch("services.nookal.httpx.AsyncClient", return_value=fake):
        result = await nookal.get_future_appointments(client, "p-100", "2026-07-22")
    assert len(result) == 1
    assert result[0]["patient_id"] == "p-100"
    url, kw = fake.calls[0]
    assert kw["params"]["patientId"] == "p-100"
    assert kw["params"]["from"] == "2026-07-22"


@pytest.mark.asyncio
async def test_get_appointments_claim_none_when_no_billing():
    client = {"id": "c1", "nookal_api_key": "nk-key"}
    payload = {"data": {"appointments": [
        {k: v for k, v in _NOOKAL_PAYLOAD["data"]["appointments"][0].items() if k != "billing"}
    ]}}
    fake = _FakeClient(_FakeResp(payload))
    with patch("services.nookal.httpx.AsyncClient", return_value=fake):
        result = await nookal.get_appointments(client, "2026-05-01", "2026-05-31")
    assert result[0]["claim"] is None
