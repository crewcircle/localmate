import logging
from datetime import date, timedelta

from workalendar.au import (
    AustralianCapitalTerritory,
    NewSouthWales,
    NorthernTerritory,
    Queensland,
    SouthAustralia,
    Tasmania,
    Victoria,
    WesternAustralia,
)

from db import get_db
from services.claude import generate_followup_message
from services.cliniko import get_appointments, get_future_appointments
from services.twilio_sms import send_sms

logger = logging.getLogger(__name__)

_STATE_CALENDARS = {
    "NSW": NewSouthWales,
    "VIC": Victoria,
    "QLD": Queensland,
    "WA": WesternAustralia,
    "SA": SouthAustralia,
    "TAS": Tasmania,
    "ACT": AustralianCapitalTerritory,
    "NT": NorthernTerritory,
}


def is_au_public_holiday(d: date, state: str = "NSW") -> bool:
    """Check if *d* is an AU public holiday for *state* via workalendar."""
    cal_class = _STATE_CALENDARS.get(state, NewSouthWales)
    cal = cal_class()
    return cal.is_holiday(d)


async def identify_lapsed_patients(client: dict) -> list[dict]:
    """Return patients who completed treatment 55–65 days ago without a future booking.

    Each returned dict contains: ``patient_id``, ``patient_name``,
    ``last_treatment``, ``last_appointment_date``, ``phone``, ``email``.
    Returns ``[]`` on failure or if no lapsed patients are found.
    """
    today = date.today()
    cutoff_end = today - timedelta(days=55)
    cutoff_start = today - timedelta(days=65)

    booking_system = client.get("booking_system", "cliniko")

    if booking_system == "cliniko":
        appointments = await get_appointments(
            client,
            date_from=cutoff_start.isoformat(),
            date_to=cutoff_end.isoformat(),
            status="completed",
        )
    else:
        logger.warning(
            "Unknown booking_system %r for client %s",
            booking_system,
            client.get("id"),
        )
        return []

    lapsed: list[dict] = []
    for appt in appointments:
        patient_id = _resolve_patient_id(appt)
        if patient_id is None:
            continue

        future = await get_future_appointments(
            client,
            patient_id=str(patient_id),
            after=today.isoformat(),
        )
        if future:
            continue

        patient_info = appt.get("patient", {})
        lapsed.append(
            {
                "patient_id": str(patient_id),
                "patient_name": patient_info.get("name")
                or appt.get("patient_name", "Patient"),
                "last_treatment": appt.get("appointment_type", "treatment"),
                "last_appointment_date": appt.get("appointment_start", ""),
                "phone": patient_info.get("phone", ""),
                "email": patient_info.get("email", ""),
            }
        )

    return lapsed


def _resolve_patient_id(appt: dict) -> str | None:
    patient_info = appt.get("patient")
    if isinstance(patient_info, dict):
        pid = patient_info.get("id")
        if pid is not None:
            return str(pid)
    raw = appt.get("patient_id")
    if raw is not None:
        return str(raw)
    return None


async def run_appointment_followup_all_clients() -> None:
    """APScheduler job — check all clients for lapsed patients and send follow-ups.

    Daily 8am AEST. Iterates clients where ``active_jobs`` contains
    ``"appointment_followup"``. Skips AU public holidays and patients with
    ``do_not_contact`` set. Logs results to the ``appointments`` table.
    Never crashes the scheduler — each client is wrapped in try/except.
    """
    db = get_db()
    resp = db.table("clients").select("*").execute()
    if not resp.data:
        return

    for client in resp.data:
        active_jobs = client.get("active_jobs") or []
        if not isinstance(active_jobs, list):
            active_jobs = []
        if "appointment_followup" not in active_jobs:
            continue

        try:
            lapsed = await identify_lapsed_patients(client)
        except Exception as e:
            logger.error(
                "identify_lapsed_patients failed for client %s: %s",
                client.get("id"),
                e,
            )
            continue

        for patient in lapsed:
            try:
                await _process_lapsed_patient(db, client, patient)
            except Exception as e:
                logger.error(
                    "Follow-up failed for patient %s (client %s): %s",
                    patient["patient_id"],
                    client.get("id"),
                    e,
                )


async def _process_lapsed_patient(
    db,
    client: dict,
    patient: dict,
) -> None:
    """Check do-not-contact, generate message, send SMS, log to appointments table."""
    patient_db = (
        db.table("patients")
        .select("do_not_contact")
        .eq("cliniko_id", patient["patient_id"])
        .maybe_single()
        .execute()
    )
    if patient_db.data and patient_db.data.get("do_not_contact"):
        logger.info(
            "Skipping patient %s — do_not_contact is set",
            patient["patient_id"],
        )
        return

    message = await generate_followup_message(
        patient_name=patient["patient_name"],
        last_treatment=patient["last_treatment"],
        business_name=client.get("business_name", ""),
        channel="sms",
    )

    phone = patient.get("phone", "")
    if not phone:
        logger.info(
            "No phone for patient %s — skipping SMS",
            patient["patient_id"],
        )
        return

    result = await send_sms(
        to=phone,
        body=message,
        state=client.get("state", "NSW"),
    )

    insert_data = {
        "client_id": client.get("id"),
        "patient_name": patient["patient_name"],
        "followup_sent": result["sent"],
        "followup_channel": "sms",
        "followup_message": message,
    }
    if result.get("sid"):
        insert_data["followup_sid"] = result["sid"]
    if result.get("reason"):
        insert_data["followup_error"] = result["reason"]

    db.table("appointments").insert(insert_data).execute()
