"""Square Appointments adapter — mirrors services/cliniko.py interface.

Uses raw httpx REST calls against the Square Bookings API.
No Square SDK dependency. Emits the canonical normalised appointment shape (see
:mod:`services.appointment_shape`) including practitioner (team_member_id) and a
``claim`` of ``None`` (Square does not surface health-fund/Medicare billing).
"""

import logging

import httpx

from config import settings
from services.appointment_shape import canonical_appointment, parse_iso_date
from services.booking_credentials import get_credential

logger = logging.getLogger(__name__)

BASE = (
    "https://connect.squareup.com"
    if getattr(settings, "square_environment", "sandbox").lower() == "production"
    else "https://connect.squareupsandbox.com"
)

_SQUARE_HEADERS = {
    "Square-Version": "2024-06-19",
    "Accept": "application/json",
    "User-Agent": "CrewCircle/1.0",
}

# --- Adapter capability metadata (read by jobs/appointment_followup.py) ---
ADAPTER_NAME = "square"
ID_COLUMN = "square_id"             # patients table column for do_not_contact lookup
CREDENTIAL_KEYS = ["square_access_token"]
SUPPORTS_REBOOK = True
AUTH_MODEL = "oauth2"


def _get_token(client: dict) -> str:
    """Resolve Square access token from client record or global settings."""
    return get_credential(client, "square_access_token") or getattr(
        settings, "square_access_token", ""
    )


def _auth_headers(client: dict) -> dict:
    """Return headers dict with Bearer auth merged onto base headers."""
    return {**_SQUARE_HEADERS, "Authorization": f"Bearer {_get_token(client)}"}


def _normalise_booking(raw: dict) -> dict:
    """Normalise a Square booking object into the canonical appointment dict.

    Practitioner id comes from the first appointment segment's ``team_member_id``.
    Square bookings do not embed the team member's display name (that needs a
    separate TeamMembers lookup), so ``practitioner_name`` is left ``None`` here —
    a future enhancement can resolve names via the Team API. Square does not surface
    health-fund/Medicare claim data, so ``claim`` is ``None``.
    """
    segments = raw.get("appointment_segments", []) or []
    first_segment = segments[0] if segments else {}
    start_at = raw.get("start_at") or first_segment.get("start_at")
    team_member_id = first_segment.get("team_member_id")
    return canonical_appointment(
        patient_id=raw.get("customer_id", ""),
        patient_name=raw.get("customer_id", "Patient"),
        patient_phone=None,
        patient_email=None,
        treatment_type=first_segment.get("service_variation_name", ""),
        appointment_date=parse_iso_date(start_at),
        status=raw.get("status", "completed"),
        practitioner_id=team_member_id,
        practitioner_name=None,
        claim=None,
    )


async def get_appointments(
    client: dict,
    date_from: str,
    date_to: str,
    status: str = "completed",
) -> list[dict]:
    """Fetch bookings from Square Bookings API for a client between dates.

    Uses Bearer auth from per-client credential store or global settings.
    Returns ``[]`` on any failure.
    """
    headers = _auth_headers(client)
    params: dict[str, str] = {
        "start_at_min": f"{date_from}T00:00:00Z",
        "start_at_max": f"{date_to}T23:59:59Z",
    }
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                f"{BASE}/v2/bookings",
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            bookings = data.get("bookings", [])
            return [_normalise_booking(b) for b in bookings]
    except Exception as e:
        logger.error("Square get_appointments failed: %s", e)
        return []


async def get_future_appointments(
    client: dict,
    patient_id: str,
    after: str,
) -> list[dict]:
    """Check if a customer has any future bookings after a given ISO date.

    Returns ``[]`` on failure or if no future bookings exist.
    """
    headers = _auth_headers(client)
    params: dict[str, str] = {
        "customer_id": patient_id,
        "start_at_min": f"{after}T00:00:00Z",
    }
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                f"{BASE}/v2/bookings",
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return [_normalise_booking(b) for b in data.get("bookings", [])]
    except Exception as e:
        logger.error("Square get_future_appointments failed: %s", e)
        return []
