"""Square Appointments adapter — mirrors services/cliniko.py interface.

Uses raw httpx REST calls against the Square Bookings API.
No Square SDK dependency.
"""

import logging
from datetime import datetime

import httpx

from config import settings

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


def _get_token(client: dict) -> str:
    """Resolve Square access token from client record or global settings."""
    return client.get("square_access_token") or getattr(settings, "square_access_token", "")


def _auth_headers(client: dict) -> dict:
    """Return headers dict with Bearer auth merged onto base headers."""
    return {**_SQUARE_HEADERS, "Authorization": f"Bearer {_get_token(client)}"}


def _parse_date(iso_str: str | None) -> str:
    """Extract YYYY-MM-DD from an ISO datetime string, or return empty string."""
    if not iso_str:
        return ""
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).date().isoformat()
    except (ValueError, TypeError):
        return ""


def _normalise_booking(raw: dict) -> dict:
    """Normalise a Square booking object into our internal appointment dict."""
    segments = raw.get("appointment_segments", [])
    first_segment = segments[0] if segments else {}
    start_at = raw.get("start_at") or first_segment.get("start_at")
    return {
        "patient_id": raw.get("customer_id", ""),
        "patient_name": raw.get("customer_id", "Patient"),
        "patient_phone": None,
        "patient_email": None,
        "treatment_type": first_segment.get("service_variation_name", ""),
        "appointment_date": _parse_date(start_at),
        "status": raw.get("status", "completed"),
    }


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
            return data.get("bookings", [])
    except Exception as e:
        logger.error("Square get_future_appointments failed: %s", e)
        return []
