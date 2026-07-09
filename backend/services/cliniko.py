import logging

import httpx

logger = logging.getLogger(__name__)
CLINIKO_BASE = "https://api.cliniko.com/v1"


async def get_appointments(
    client: dict,
    date_from: str,
    date_to: str,
    status: str = "completed",
) -> list[dict]:
    """Fetch appointments from Cliniko API for a client between dates.

    Uses Bearer auth from *per-client* credential store (``client['cliniko_api_key']``).
    Returns ``[]`` on any failure.
    """
    headers = {
        "Authorization": f"Bearer {client.get('cliniko_api_key', '')}",
        "Accept": "application/json",
        "User-Agent": "CrewCircle/1.0",
    }
    params = {
        "appointment_start_from": date_from,
        "appointment_start_to": date_to,
        "status": status,
    }
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                f"{CLINIKO_BASE}/appointments",
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("appointments", [])
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
    headers = {
        "Authorization": f"Bearer {client.get('cliniko_api_key', '')}",
        "Accept": "application/json",
        "User-Agent": "CrewCircle/1.0",
    }
    params = {
        "patient_id": patient_id,
        "appointment_start_from": after,
    }
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                f"{CLINIKO_BASE}/appointments",
                headers=headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("appointments", [])
    except Exception as e:
        logger.error("Cliniko get_future_appointments failed: %s", e)
        return []
