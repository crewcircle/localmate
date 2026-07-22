"""Nookal booking adapter (full, real).

Account API-key auth against ``https://api.nookal.com/production/v2/``. Uses
``getAppointments`` with date/status filters and normalises each item to the
canonical shape (see :mod:`services.appointment_shape`) including practitioner +
best-effort claim fields. ``SUPPORTS_REBOOK=True``.

Nookal's exact ``getAppointments`` param names / completed-status value / paging
are not fully documented publicly; the normaliser is defensive and returns ``[]``
on any error.
"""
import logging
from datetime import datetime

import httpx

from config import settings
from services.appointment_shape import canonical_appointment, make_claim
from services.booking_credentials import get_credential

logger = logging.getLogger(__name__)
NOOKAL_BASE = "https://api.nookal.com/production/v2"

# --- Adapter capability metadata (read by jobs/appointment_followup.py) ---
ADAPTER_NAME = "nookal"
ID_COLUMN = "nookal_id"             # patients table column for do_not_contact lookup
CREDENTIAL_KEYS = ["nookal_api_key"]
SUPPORTS_REBOOK = True
AUTH_MODEL = "api_key"

# Map our internal status to Nookal's appointment status labels.
_STATUS_MAP = {
    "completed": "Completed",
    "cancelled": "Cancelled",
    "noshow": "No Show",
}


def _parse_date(value: str | None) -> str:
    """Extract YYYY-MM-DD from a Nookal date/datetime string, or return ``""``."""
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except (ValueError, TypeError):
        # Nookal sometimes returns plain "YYYY-MM-DD" dates — accept directly.
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]
        return ""


def _extract_claim(item: dict) -> dict | None:
    """Best-effort claim extraction from Nookal billing fields, else ``None``."""
    billing = item.get("billing") or item.get("invoice") or {}
    if not isinstance(billing, dict) or not billing:
        return None
    return make_claim(
        claim_type=billing.get("claim_type") or billing.get("type"),
        fund=billing.get("fund") or billing.get("health_fund"),
        gap_amount=billing.get("gap_amount"),
    )


def _normalise(item: dict) -> dict:
    """Normalise a Nookal appointment object into the canonical shape.

    Nookal appointments carry ``practitionerId``/``practitionerName`` directly. The
    patient block may be nested under ``patient`` or flattened to ``patientId`` /
    ``patientName`` — handle both.
    """
    patient = item.get("patient") or {}
    if not isinstance(patient, dict):
        patient = {}
    prac_id = item.get("practitionerId") or item.get("practitioner_id")
    return canonical_appointment(
        patient_id=item.get("patientId") or item.get("patient_id") or patient.get("id"),
        patient_name=item.get("patientName") or item.get("patient_name") or patient.get("name"),
        patient_phone=item.get("patientPhone") or item.get("patient_phone") or patient.get("phone"),
        patient_email=item.get("patientEmail") or item.get("patient_email") or patient.get("email"),
        treatment_type=(
            item.get("appointmentType")
            or item.get("appointment_type")
            or item.get("type")
            or item.get("name")
            or ""
        ),
        appointment_date=_parse_date(
            item.get("date") or item.get("appointmentDate") or item.get("appointment_date") or item.get("start")
        ),
        status=item.get("status", "completed"),
        practitioner_id=prac_id,
        practitioner_name=item.get("practitionerName") or item.get("practitioner_name"),
        claim=_extract_claim(item),
    )


def _api_key(client: dict) -> str:
    return get_credential(client, "nookal_api_key") or getattr(settings, "nookal_api_key", "")


def _appointments_from(data: dict) -> list[dict]:
    """Pull the appointments list from a Nookal response, handling wrapper shapes."""
    if not isinstance(data, dict):
        return []
    for key in ("appointments", "data"):
        node = data.get(key)
        if isinstance(node, dict) and isinstance(node.get("appointments"), list):
            return node["appointments"]
        if isinstance(node, list):
            return node
    return []


async def get_appointments(
    client: dict,
    date_from: str,
    date_to: str,
    status: str = "completed",
) -> list[dict]:
    """Fetch appointments from Nookal for a client between dates.

    Uses account API-key auth (query param ``api_key``). Returns ``[]`` on any
    failure.
    """
    api_key = _api_key(client)
    if not api_key:
        logger.error("Nookal get_appointments: no api_key configured for client %s", client.get("id"))
        return []
    params = {
        "api_key": api_key,
        "from": date_from,
        "to": date_to,
        "status": _STATUS_MAP.get(status, status),
    }
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                f"{NOOKAL_BASE}/getAppointments",
                params=params,
                headers={"Accept": "application/json", "User-Agent": "CrewCircle/1.0"},
                timeout=30,
            )
            resp.raise_for_status()
            return [_normalise(a) for a in _appointments_from(resp.json())]
    except Exception as e:
        logger.error("Nookal get_appointments failed: %s", e)
        return []


async def get_future_appointments(
    client: dict,
    patient_id: str,
    after: str,
) -> list[dict]:
    """Check if a patient has any future bookings after a given ISO date.

    Returns ``[]`` on failure or if no future appointments exist.
    """
    api_key = _api_key(client)
    if not api_key:
        logger.error("Nookal get_future_appointments: no api_key configured")
        return []
    params = {
        "api_key": api_key,
        "patientId": patient_id,
        "from": after,
    }
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                f"{NOOKAL_BASE}/getAppointments",
                params=params,
                headers={"Accept": "application/json", "User-Agent": "CrewCircle/1.0"},
                timeout=30,
            )
            resp.raise_for_status()
            return [_normalise(a) for a in _appointments_from(resp.json())]
    except Exception as e:
        logger.error("Nookal get_future_appointments failed: %s", e)
        return []
