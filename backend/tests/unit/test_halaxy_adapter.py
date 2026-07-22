"""Tests for the Halaxy booking adapter (OAuth2 + FHIR, mocked httpx)."""
import pytest
from unittest.mock import patch

import httpx

from services import halaxy


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=httpx.Request("POST", "x"), response=httpx.Response(self.status_code)
            )


class _HalaxyFakeClient:
    """One fake client handling the token POST and the FHIR GET (separate AsyncClient
    calls in the adapter share this via the patch)."""

    def __init__(self, token_resp, fhir_resp):
        self._token = token_resp
        self._fhir = fhir_resp
        self.post_calls = []
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kw):
        self.post_calls.append((url, kw))
        if isinstance(self._token, Exception):
            raise self._token
        return self._token

    async def get(self, url, **kw):
        self.get_calls.append((url, kw))
        if isinstance(self._fhir, Exception):
            raise self._fhir
        return self._fhir


_TOKEN_PAYLOAD = {"access_token": "tok-abc", "expires_in": 900}

_FHIR_BUNDLE = {
    "resourceType": "Bundle",
    "entry": [
        {
            "resource": {
                "resourceType": "Appointment",
                "id": "appt-1",
                "status": "fulfilled",
                "start": "2026-05-20T09:00:00+10:00",
                "serviceType": [{"coding": [{"display": "General Consult"}]}],
                "participant": [
                    {"actor": {"reference": "Patient/p-200", "display": "Bob Smith"}},
                    {"actor": {"reference": "Practitioner/prac-9", "display": "Dr Nguyen"}},
                ],
            }
        }
    ],
}


@pytest.fixture(autouse=True)
def _clear_token_cache():
    halaxy._token_cache.clear()
    yield
    halaxy._token_cache.clear()


def test_halaxy_metadata():
    assert halaxy.ADAPTER_NAME == "halaxy"
    assert halaxy.ID_COLUMN == "halaxy_id"
    assert halaxy.CREDENTIAL_KEYS == ["halaxy_client_id", "halaxy_client_secret"]
    assert halaxy.SUPPORTS_REBOOK is True
    assert halaxy.AUTH_MODEL == "oauth2_client_credentials"


@pytest.mark.asyncio
async def test_get_appointments_fhir_to_canonical():
    client = {"id": "c1", "halaxy_client_id": "cid", "halaxy_client_secret": "sec"}
    fake = _HalaxyFakeClient(_FakeResp(_TOKEN_PAYLOAD), _FakeResp(_FHIR_BUNDLE))
    with patch("services.halaxy.httpx.AsyncClient", return_value=fake):
        result = await halaxy.get_appointments(client, "2026-05-01", "2026-05-31", "completed")

    assert len(result) == 1
    appt = result[0]
    assert appt["patient_id"] == "p-200"
    assert appt["patient_name"] == "Bob Smith"
    assert appt["practitioner_id"] == "prac-9"
    assert appt["practitioner_name"] == "Dr Nguyen"
    assert appt["treatment_type"] == "General Consult"
    assert appt["appointment_date"] == "2026-05-20"
    assert appt["status"] == "completed"  # FHIR "fulfilled" -> "completed"
    assert appt["claim"] is None

    # FHIR GET sent with application/fhir+json + Bearer token.
    assert len(fake.get_calls) == 1
    url, kw = fake.get_calls[0]
    assert url.endswith("/Appointment")
    assert kw["headers"]["Accept"] == "application/fhir+json"
    assert kw["headers"]["Authorization"] == "Bearer tok-abc"
    # date range expressed as ge/le, completed mapped to fulfilled.
    assert kw["params"]["date"] == ["ge2026-05-01", "le2026-05-31"]
    assert kw["params"]["status"] == "fulfilled"


@pytest.mark.asyncio
async def test_token_fetch_failure_returns_empty():
    client = {"id": "c1", "halaxy_client_id": "cid", "halaxy_client_secret": "sec"}
    fake = _HalaxyFakeClient(httpx.ConnectError("no token"), _FakeResp(_FHIR_BUNDLE))
    with patch("services.halaxy.httpx.AsyncClient", return_value=fake):
        result = await halaxy.get_appointments(client, "2026-05-01", "2026-05-31")
    assert result == []
    # No FHIR GET attempted when the token could not be obtained.
    assert fake.get_calls == []


@pytest.mark.asyncio
async def test_missing_credentials_returns_empty():
    client = {"id": "c1"}  # no client_id/secret, no global fallback
    with patch("services.halaxy.httpx.AsyncClient") as mock_client:
        result = await halaxy.get_appointments(client, "2026-05-01", "2026-05-31")
    assert result == []
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_get_future_appointments_queries_by_patient():
    client = {"id": "c1", "halaxy_client_id": "cid", "halaxy_client_secret": "sec"}
    fake = _HalaxyFakeClient(_FakeResp(_TOKEN_PAYLOAD), _FakeResp(_FHIR_BUNDLE))
    with patch("services.halaxy.httpx.AsyncClient", return_value=fake):
        result = await halaxy.get_future_appointments(client, "p-200", "2026-07-22")
    assert len(result) == 1
    url, kw = fake.get_calls[0]
    assert kw["params"]["patient"] == "p-200"
    assert kw["params"]["date"] == "ge2026-07-22"


@pytest.mark.asyncio
async def test_token_cached_across_calls():
    """The Bearer token is cached so a second call does not re-POST to the token endpoint."""
    client = {"id": "c1", "halaxy_client_id": "cid", "halaxy_client_secret": "sec"}
    fake = _HalaxyFakeClient(_FakeResp(_TOKEN_PAYLOAD), _FakeResp(_FHIR_BUNDLE))
    with patch("services.halaxy.httpx.AsyncClient", return_value=fake):
        await halaxy.get_appointments(client, "2026-05-01", "2026-05-31")
        await halaxy.get_future_appointments(client, "p-200", "2026-07-22")
    # Only one token POST across both calls.
    assert len(fake.post_calls) == 1
    assert len(fake.get_calls) == 2
