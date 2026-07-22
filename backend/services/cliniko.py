"""Cliniko booking adapter.

Emits the canonical normalised appointment shape (see
:mod:`services.appointment_shape`) including practitioner + best-effort claim
fields. Cliniko appointments expose a ``practitioner`` link; billing/claim data
lives on invoices rather than the appointments endpoint, so ``claim`` stays
``None`` here unless billing fields are present on the appointment payload.
"""
import logging
from datetime import datetime

import httpx

from services.appointment_shape import canonical_appointment, make_claim
from services.booking_credentials import get_credential

logger = logging.getLogger(__name__)
CLINIKO_BASE = "https://api.cliniko.com/v1"

# --- Adapter capability metadata (read by jobs/appointment_followup.py) ---
ADAPTER_NAME = "cliniko"
ID_COLUMN = "cliniko_id"            # patients table column for do_not_contact lookup
CREDENTIAL_KEYS = ["cliniko_api_key"]
SUPPORTS_REBOOK = True
AUTH_MODEL = "api_key"


def _parse_date(iso_str: str | None) -> str:
    """Extract YYYY-MM-DD from an ISO datetime string, or return empty string."""
    if not iso_str:
        return ""
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).date().isoformat()
    except (ValueError, TypeError):
        return ""


def _practitioner(appt: dict) -> tuple[str | None, str | None]:
    """Extract (practitioner_id, practitioner_name) from a Cliniko appointment.

    Cliniko may embed ``practitioner_id`` directly, nest a ``practitioner`` object,
    or carry it under ``links``. Handle each defensively.
    """
    prac_id = appt.get("practitioner_id")
    prac_name = appt.get("practitioner_name")
    practitioner = appt.get("practitioner")
    if isinstance(practitioner, dict):
        prac_id = prac_id or practitioner.get("id")
        prac_name = prac_name or practitioner.get("name")
    if not prac_id:
        for link in appt.get("links", []) or []:
            if isinstance(link, dict) and link.get("rel") == "practitioner":
                prac_id = prac_id or link.get("id")
                break
    return (str(prac_id) if prac_id else None, prac_name)


def _extract_claim(appt: dict) -> dict | None:
    """Best-effort claim extraction. Cliniko surfaces billing on invoices, not the
    appointments endpoint — returns ``None`` unless billing fields are present."""
    billing = appt.get("billing") or appt.get("invoice")
    if not isinstance(billing, dict):
        return None
    return make_claim(
        claim_type=billing.get("claim_type") or billing.get("type"),
        fund=billing.get("fund") or billing.get("health_fund"),
        gap_amount=billing.get("gap_amount"),
    )


def _normalise(appt: dict) -> dict:
    """Normalise a raw Cliniko appointment into the canonical shape."""
    patient = appt.get("patient") or {}
    if not isinstance(patient, dict):
        patient = {}
    prac_id, prac_name = _practitioner(appt)
    return canonical_appointment(
        patient_id=patient.get("id"),
        patient_name=patient.get("name"),
        patient_phone=patient.get("phone"),
        patient_email=patient.get("email"),
        treatment_type=appt.get("appointment_type", ""),
        appointment_date=_parse_date(appt.get("appointment_start")),
        status=appt.get("status", "completed"),
        practitioner_id=prac_id,
        practitioner_name=prac_name,
        claim=_extract_claim(appt),
    )


def _headers(client: dict) -> dict:
    return {
        "Authorization": f"Bearer {get_credential(client, 'cliniko_api_key')}",
        "Accept": "application/json",
        "User-Agent": "CrewCircle/1.0",
    }


async def get_appointments(
    client: dict,
    date_from: str,
    date_to: str,
    status: str = "completed",
) -> list[dict]:
    """Fetch appointments from Cliniko API for a client between dates.

    Uses Bearer auth from the per-client credential store (``cliniko_api_key``).
    Returns ``[]`` on any failure.
    """
    params = {
        "appointment_start_from": date_from,
        "appointment_start_to": date_to,
        "status": status,
    }
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                f"{CLINIKO_BASE}/appointments",
                headers=_headers(client),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return [_normalise(a) for a in data.get("appointments", [])]
    except Exception as e:
        logger.error("Cliniko get_appointments failed: %s", e)
        return []


async def get_future_appointments(
    client: dict,
    patient_id: str,
    after: str,
) -> list[dict]:
    """Check if a patient has any future bookings after a given ISO date.

    Returns ``[]`` on failure or if no future appointments exist.
    """
    params = {
        "patient_id": patient_id,
        "appointment_start_from": after,
    }
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                f"{CLINIKO_BASE}/appointments",
                headers=_headers(client),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return [_normalise(a) for a in data.get("appointments", [])]
    except Exception as e:
        logger.error("Cliniko get_future_appointments failed: %s", e)
        return []
