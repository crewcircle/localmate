"""Halaxy booking adapter (full, real — OAuth2 client_credentials + FHIR).

Auth: OAuth2 ``client_credentials`` → a Bearer token cached ~15 min per client.
Endpoints: FHIR ``GET /Appointment?date=…&status=…`` and
``GET /Appointment?patient={id}&date=ge{after}`` (``Accept: application/fhir+json``).
FHIR ``Appointment.participant`` → ``Practitioner`` reference supplies the
practitioner. Rate-limit aware (500 req/min sliding window): retries once with
backoff on HTTP 429. ``SUPPORTS_REBOOK=True``.

Halaxy's API is a paid add-on per clinic account; Rebook only works for Halaxy
clients who have enabled it. ``[]`` is returned on any error, including a
token-fetch failure.
"""
import asyncio
import logging
import time

import httpx

from config import settings
from services.appointment_shape import canonical_appointment, parse_iso_date
from services.booking_credentials import get_credential

logger = logging.getLogger(__name__)

_HALAXY_BASES = {
    "au": "https://au-api.halaxy.com/main",
    "eu": "https://eu-api.halaxy.com/main",
}

# Token cache: client_id -> (access_token, expiry_epoch). Tokens last ~15 min; we
# refresh a little early (30s margin) so a request never hits an expired token.
_token_cache: dict[str, tuple[str, float]] = {}
_TOKEN_MARGIN = 30.0
# Rate-limit backoff: one retry on HTTP 429 before giving up.
_429_BACKOFF = 1.0

# --- Adapter capability metadata (read by jobs/appointment_followup.py) ---
ADAPTER_NAME = "halaxy"
ID_COLUMN = "halaxy_id"             # patients table column for do_not_contact lookup
CREDENTIAL_KEYS = ["halaxy_client_id", "halaxy_client_secret"]
SUPPORTS_REBOOK = True
AUTH_MODEL = "oauth2_client_credentials"


def _base_url() -> str:
    env = getattr(settings, "halaxy_environment", "au").lower()
    return _HALAXY_BASES.get(env, _HALAXY_BASES["au"])


def _client_credentials(client: dict) -> tuple[str, str]:
    cid = get_credential(client, "halaxy_client_id") or getattr(settings, "halaxy_client_id", "")
    secret = get_credential(client, "halaxy_client_secret") or getattr(settings, "halaxy_client_secret", "")
    return cid, secret


async def _get_token(client: dict) -> str:
    """Obtain (and cache) a Halaxy Bearer token via client_credentials.

    Returns ``""`` on any failure (missing credentials or token endpoint error).
    """
    cid, secret = _client_credentials(client)
    if not cid or not secret:
        logger.error("Halaxy: missing client_id/secret for client %s", client.get("id"))
        return ""
    now = time.time()
    cached = _token_cache.get(cid)
    if cached and cached[1] > now + _TOKEN_MARGIN:
        return cached[0]
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.post(
                f"{_base_url()}/token",
                data={"grant_type": "client_credentials", "client_id": cid, "client_secret": secret},
                headers={"Accept": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        token = data.get("access_token", "")
        expires_in = float(data.get("expires_in", 900))
        _token_cache[cid] = (token, now + expires_in)
        return token
    except Exception as e:
        logger.error("Halaxy token fetch failed: %s", e)
        return ""


# Map FHIR Appointment.status to our internal status labels.
_FHIR_STATUS_MAP = {
    "fulfilled": "completed",
    "arrived": "completed",
    "cancelled": "cancelled",
    "noshow": "noshow",
    "booked": "booked",
    "proposed": "proposed",
}


def _map_status(fhir_status: str | None) -> str:
    if not fhir_status:
        return "completed"
    return _FHIR_STATUS_MAP.get(fhir_status, fhir_status)


def _service_type(appt: dict) -> str:
    """Extract a treatment-type label from a FHIR Appointment's serviceType."""
    for st in appt.get("serviceType") or []:
        if not isinstance(st, dict):
            continue
        for coding in st.get("coding") or []:
            if coding.get("display"):
                return coding["display"]
            if coding.get("code"):
                return coding["code"]
    return ""


def _participants(appt: dict) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (patient_id, patient_name, practitioner_id, practitioner_name).

    FHIR Appointment.participant carries actor references like
    ``Patient/{id}`` / ``Practitioner/{id}`` with an optional ``display``.
    """
    patient_id = patient_name = practitioner_id = practitioner_name = None
    for p in appt.get("participant") or []:
        actor = (p or {}).get("actor") or {}
        ref = actor.get("reference", "")
        display = actor.get("display")
        if ref.startswith("Practitioner/"):
            practitioner_id = ref.split("/", 1)[1]
            practitioner_name = display or practitioner_name
        elif ref.startswith("Patient/"):
            patient_id = ref.split("/", 1)[1]
            patient_name = display or patient_name
    return patient_id, patient_name, practitioner_id, practitioner_name


def _normalise_fhir(entry: dict) -> dict:
    """Normalise a FHIR bundle entry into the canonical appointment shape."""
    appt = entry.get("resource", entry) if isinstance(entry, dict) else {}
    patient_id, patient_name, practitioner_id, practitioner_name = _participants(appt)
    return canonical_appointment(
        patient_id=patient_id,
        patient_name=patient_name,
        treatment_type=_service_type(appt),
        appointment_date=parse_iso_date(appt.get("start")),
        status=_map_status(appt.get("status")),
        practitioner_id=practitioner_id,
        practitioner_name=practitioner_name,
        claim=None,  # FHIR Claim/ExplanationOfBenefit lookup is a separate best-effort call
    )


def _entries_from(data: dict) -> list[dict]:
    """Pull the FHIR bundle entries from a search response."""
    if not isinstance(data, dict):
        return []
    entries = data.get("entry")
    if isinstance(entries, list):
        return entries
    return []


async def _fhir_get(url: str, token: str, params: dict) -> httpx.Response | None:
    """GET a FHIR endpoint with rate-limit (429) backoff. Returns the response or
    ``None`` on transport/HTTP error after the single retry."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/fhir+json",
        "User-Agent": "CrewCircle/1.0",
    }
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient() as session:
                resp = await session.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 429 and attempt == 1:
                logger.warning("Halaxy 429 rate limit — backing off and retrying once")
                await asyncio.sleep(_429_BACKOFF)
                continue
            return resp
        except Exception as e:
            logger.error("Halaxy FHIR GET failed (attempt %d): %s", attempt, e)
            return None
    # Unreachable — kept as defensive guard.
    return None  # pragma: no cover


async def get_appointments(
    client: dict,
    date_from: str,
    date_to: str,
    status: str = "completed",
) -> list[dict]:
    """Fetch appointments from Halaxy (FHIR) for a client between dates.

    Maps our ``status="completed"`` to the FHIR ``fulfilled`` status. Returns
    ``[]`` on any failure, including a token-fetch failure.
    """
    token = await _get_token(client)
    if not token:
        return []
    fhir_status = "fulfilled" if status == "completed" else status
    params = {
        "date": [f"ge{date_from}", f"le{date_to}"],
        "status": fhir_status,
    }
    resp = await _fhir_get(f"{_base_url()}/Appointment", token, params)
    if resp is None:
        return []
    try:
        resp.raise_for_status()
        return [_normalise_fhir(e) for e in _entries_from(resp.json())]
    except Exception as e:
        logger.error("Halaxy get_appointments parse failed: %s", e)
        return []


async def get_future_appointments(
    client: dict,
    patient_id: str,
    after: str,
) -> list[dict]:
    """Check if a patient has any future bookings after a given ISO date.

    Returns ``[]`` on failure or if no future appointments exist.
    """
    token = await _get_token(client)
    if not token:
        return []
    params = {"patient": patient_id, "date": f"ge{after}"}
    resp = await _fhir_get(f"{_base_url()}/Appointment", token, params)
    if resp is None:
        return []
    try:
        resp.raise_for_status()
        return [_normalise_fhir(e) for e in _entries_from(resp.json())]
    except Exception as e:
        logger.error("Halaxy get_future_appointments parse failed: %s", e)
        return []
