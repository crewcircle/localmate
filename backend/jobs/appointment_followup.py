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
from services import cliniko as cliniko_adapter
from services import square_appointments as square_adapter
from services import nookal as nookal_adapter
from services import halaxy as halaxy_adapter
from services import hotdoc as hotdoc_adapter
from services import jane as jane_adapter
from services import practicepal as practicepal_adapter

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

# All seven booking adapters. Stub adapters (hotdoc/jane/practicepal) register
# with SUPPORTS_REBOOK=False so the job fails safe instead of 404ing.
_BOOKING_ADAPTERS = {
    "cliniko": cliniko_adapter,
    "square": square_adapter,
    "nookal": nookal_adapter,
    "halaxy": halaxy_adapter,
    "hotdoc": hotdoc_adapter,
    "jane": jane_adapter,
    "practicepal": practicepal_adapter,
}


def get_booking_adapter(booking_system: str):  # type: ignore[no-untyped-def]
    """Return the adapter module for *booking_system*, or None if unsupported."""
    adapter = _BOOKING_ADAPTERS.get(booking_system)
    if adapter is None:
        logger.warning("Unsupported booking_system %r — skipping", booking_system)
    return adapter


def is_au_public_holiday(d: date, state: str = "NSW") -> bool:
    """Check if *d* is an AU public holiday for *state* via workalendar."""
    cal_class = _STATE_CALENDARS.get(state, NewSouthWales)
    cal = cal_class()
    return cal.is_holiday(d)


async def _upsert_practitioners(db, client_id, booking_system: str, appointments: list[dict]) -> None:
    """UPSERT ``practitioners`` rows for each unique practitioner seen (C5).

    Records external_id + name + booking_system so opt-outs and the dashboard have
    rows even before a follow-up is ever sent. Best-effort: per-row errors are logged.
    """
    if not client_id or not appointments:
        return
    seen: dict[str, str | None] = {}
    for appt in appointments:
        pid = appt.get("practitioner_id")
        if pid:
            seen[str(pid)] = appt.get("practitioner_name")
    if not seen:
        return
    for ext_id, name in seen.items():
        try:
            db.table("practitioners").upsert(
                {
                    "client_id": client_id,
                    "booking_system": booking_system,
                    "external_id": ext_id,
                    "name": name,
                },
                on_conflict="client_id,booking_system,external_id",
            ).execute()
        except Exception as e:
            logger.error("practitioner upsert failed for %s/%s: %s", booking_system, ext_id, e)


async def identify_lapsed_patients(client: dict) -> list[dict]:
    """Return patients who completed treatment 55–65 days ago without a future booking.

    Reads the **canonical normalised** appointment shape (patient_id, patient_name,
    patient_phone, patient_email, treatment_type, appointment_date, status,
    practitioner_id, practitioner_name, claim) — NOT Cliniko-specific raw keys.
    Returns the canonical dicts for lapsed patients (truthy non-empty
    ``get_future_appointments`` ⇒ patient has a future booking ⇒ not lapsed).

    After fetching, UPSERTs ``practitioners`` rows (C5) so opt-outs / dashboard have
    records. Returns ``[]`` on failure, for unsupported systems, or when no lapsed
    patients are found.
    """
    today = date.today()
    cutoff_end = today - timedelta(days=55)
    cutoff_start = today - timedelta(days=65)

    booking_system = client.get("booking_system", "cliniko")
    adapter = get_booking_adapter(booking_system)
    if adapter is None:
        return []
    if not getattr(adapter, "SUPPORTS_REBOOK", True):
        logger.info(
            "booking_system %s does not support rebook — skipping", booking_system
        )
        return []

    appointments = await adapter.get_appointments(
        client,
        date_from=cutoff_start.isoformat(),
        date_to=cutoff_end.isoformat(),
        status="completed",
    )

    # Practitioner upsert (C5): record every practitioner seen so opt-outs + the
    # dashboard have rows. Best-effort — never blocks the follow-up loop.
    try:
        await _upsert_practitioners(get_db(), client.get("id"), booking_system, appointments)
    except Exception as e:
        logger.error("practitioner upsert failed for client %s: %s", client.get("id"), e)

    lapsed: list[dict] = []
    for appt in appointments:
        patient_id = appt.get("patient_id")
        if not patient_id:
            continue

        future = await adapter.get_future_appointments(
            client,
            patient_id=str(patient_id),
            after=today.isoformat(),
        )
        if future:
            continue

        lapsed.append(appt)

    return lapsed


async def _enqueue_sms(arq_pool, to: str, body: str, state: str) -> tuple[str | None, bool, str | None]:
    """Enqueue a durable ``send_sms_task`` via arq (C4 outbound migration).

    SMS sends route through the Phase 0 durable Twilio wrapper instead of calling
    ``services.twilio_sms.send_sms`` directly. Returns ``(sid, sent, error)``:
    ``sid`` is the arq job id (the real Twilio SID is recorded inside
    ``send_sms_task``), ``sent`` is True when the enqueue succeeded, and ``error``
    is a failure reason or ``None``.
    """
    pool = arq_pool
    created_pool = False
    if pool is None:
        from task_queue import get_arq_pool

        try:
            pool = await get_arq_pool()
            created_pool = True
        except Exception as e:
            logger.error("arq pool unavailable for SMS enqueue: %s", e)
            return None, False, f"enqueue_failed: {e}"
    try:
        job = await pool.enqueue_job("send_sms_task", to, body, state)
    except Exception as e:
        logger.error("enqueue_job(send_sms_task) failed: %s", e)
        return None, False, f"enqueue_failed: {e}"
    finally:
        if created_pool:
            try:
                await pool.close()
            except Exception:
                pass
    # enqueue_job returns None when a job with the same id is already queued —
    # treat that as a successfully queued send.
    if job is None:
        return None, True, None
    return getattr(job, "job_id", None), True, None


async def run_appointment_followup_all_clients(arq_pool=None) -> None:  # type: ignore[no-untyped-def]
    """APScheduler job — check all clients for lapsed patients and send follow-ups.

    Daily 8am AEST. Iterates clients where ``active_jobs`` contains
    ``"appointment_followup"``. Skips AU public holidays and patients with
    ``do_not_contact`` set (patient- OR practitioner-level). Logs results to the
    ``appointments`` table. Never crashes the scheduler — each client is wrapped in
    try/except. ``arq_pool`` (the worker's ``ctx["redis"]``) is threaded through so
    outbound SMS sends enqueue on the existing pool rather than opening new ones.
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

        booking_system = client.get("booking_system", "cliniko")
        adapter = get_booking_adapter(booking_system)
        if adapter is not None and not getattr(adapter, "SUPPORTS_REBOOK", True):
            logger.info(
                "Client %s booking_system %s unsupported — skipping (adapter_unsupported)",
                client.get("id"),
                booking_system,
            )
            try:
                db.table("appointments").insert(
                    {
                        "client_id": client.get("id"),
                        "patient_id": "adapter_unsupported",
                        "appointment_date": date.today().isoformat(),
                        "followup_error": "adapter_unsupported",
                    }
                ).execute()
            except Exception as e:
                logger.error(
                    "failed to write adapter_unsupported marker for client %s: %s",
                    client.get("id"),
                    e,
                )
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
                await _process_lapsed_patient(db, client, patient, arq_pool)
            except Exception as e:
                logger.error(
                    "Follow-up failed for patient %s (client %s): %s",
                    patient.get("patient_id"),
                    client.get("id"),
                    e,
                )


async def _process_lapsed_patient(
    db,
    client: dict,
    patient: dict,
    arq_pool=None,  # type: ignore[no-untyped-def]
) -> None:
    """Check do-not-contact, generate message, send SMS, log to appointments table.

    ``patient`` is a canonical normalised appointment dict. Uses
    ``adapter.ID_COLUMN`` for the patient do_not_contact lookup (fixes the
    hardcoded cliniko/square id-column dispatch bug) and additionally checks
    ``practitioners.do_not_contact`` (whole-practitioner suppression). Threads
    ``practitioner_name`` and ``claim_type`` into message generation, routes the SMS
    through the durable ``send_sms_task`` (C4), and writes followup/practitioner/
    claim columns to ``appointments`` (columns added in migration 016).
    """
    booking_system = client.get("booking_system", "cliniko")
    adapter = get_booking_adapter(booking_system)
    id_column = getattr(adapter, "ID_COLUMN", "cliniko_id") if adapter else "cliniko_id"
    client_id = client.get("id")
    patient_id = patient.get("patient_id")

    # --- Patient-level do-not-contact (uses adapter.ID_COLUMN) ---
    try:
        patient_db = (
            db.table("patients")
            .select("do_not_contact")
            .eq("client_id", client_id)
            .eq(id_column, patient_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error(
            "patients lookup failed for %s (client %s): %s",
            patient_id,
            client_id,
            e,
        )
        patient_db = type("FakeResult", (), {"data": None})()

    if patient_db.data and patient_db.data.get("do_not_contact"):
        logger.info(
            "Skipping patient %s — do_not_contact is set",
            patient_id,
        )
        return

    # --- Practitioner-level do-not-contact (whole-practitioner suppression) ---
    practitioner_id = patient.get("practitioner_id")
    if practitioner_id:
        try:
            prac_db = (
                db.table("practitioners")
                .select("do_not_contact")
                .eq("client_id", client_id)
                .eq("booking_system", booking_system)
                .eq("external_id", str(practitioner_id))
                .maybe_single()
                .execute()
            )
        except Exception as e:
            logger.error(
                "practitioners lookup failed for %s (client %s): %s",
                practitioner_id,
                client_id,
                e,
            )
            prac_db = type("FakeResult", (), {"data": None})()
        if prac_db.data and prac_db.data.get("do_not_contact"):
            logger.info(
                "Skipping patient %s — practitioner %s do_not_contact is set",
                patient_id,
                practitioner_id,
            )
            return

    # --- Message generation (thread practitioner_name + claim_type) ---
    claim = patient.get("claim") or {}
    message = await generate_followup_message(
        patient_name=patient.get("patient_name", "Patient"),
        last_treatment=patient.get("treatment_type", "treatment"),
        business_name=client.get("business_name", ""),
        channel="sms",
        practitioner_name=patient.get("practitioner_name"),
        claim_type=claim.get("type"),
    )

    # --- Outbound SMS via durable arq task (C4) ---
    phone = patient.get("patient_phone") or ""
    if not phone:
        logger.info(
            "No phone for patient %s — skipping SMS",
            patient_id,
        )
        return

    sid, sent, error = await _enqueue_sms(arq_pool, phone, message, client.get("state", "NSW"))

    # --- Log to appointments (followup/practitioner/claim columns added in 016) ---
    insert_data = {
        "client_id": client_id,
        "patient_id": str(patient_id),
        "patient_name": patient.get("patient_name"),
        "patient_phone": phone,
        "patient_email": patient.get("patient_email"),
        "treatment_type": patient.get("treatment_type", ""),
        "appointment_date": patient.get("appointment_date") or date.today().isoformat(),
        "status": patient.get("status", "completed"),
        "practitioner_id": str(practitioner_id) if practitioner_id else None,
        "practitioner_name": patient.get("practitioner_name"),
        "claim_type": claim.get("type"),
        "claim_fund": claim.get("fund"),
        "claim_gap_amount": claim.get("gap_amount"),
        "followup_sent": sent,
        "followup_channel": "sms",
        "followup_message": message,
    }
    if sid:
        insert_data["followup_sid"] = sid
    if error:
        insert_data["followup_error"] = error

    try:
        db.table("appointments").insert(insert_data).execute()
    except Exception as e:
        logger.error("appointments insert failed for patient %s: %s", patient_id, e)
