"""Tests for lapsed patient identification, canonical-shape handling, multi-
practitioner do-not-contact, ID_COLUMN dispatch, claim threading, practitioner
upsert and the durable SMS enqueue path."""
import sys
import types

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date


def _install_workalendar_au_stub():
    mod = types.ModuleType("workalendar.au")
    from workalendar.oceania import (
        AustralianCapitalTerritory,
        NewSouthWales,
        NorthernTerritory,
        Queensland,
        SouthAustralia,
        Tasmania,
        Victoria,
        WesternAustralia,
    )
    mod.AustralianCapitalTerritory = AustralianCapitalTerritory
    mod.NewSouthWales = NewSouthWales
    mod.NorthernTerritory = NorthernTerritory
    mod.Queensland = Queensland
    mod.SouthAustralia = SouthAustralia
    mod.Tasmania = Tasmania
    mod.Victoria = Victoria
    mod.WesternAustralia = WesternAustralia
    sys.modules["workalendar.au"] = mod


_install_workalendar_au_stub()


def _canonical_appt(**overrides):
    """A canonical normalised appointment dict (the Square flat shape extended)."""
    appt = {
        "patient_id": "pat-001",
        "patient_name": "John Smith",
        "patient_phone": "+61412345678",
        "patient_email": "john@example.com.au",
        "treatment_type": "Dental Clean",
        "appointment_date": "2026-05-15",
        "status": "completed",
        "practitioner_id": "prac-01",
        "practitioner_name": "Dr Chen",
        "claim": {"type": "gap", "fund": "Bupa", "gap_amount": 35.0},
    }
    appt.update(overrides)
    return appt


def _canonical_appointment_future():
    return _canonical_appt(appointment_date="2099-01-01", status="booked")


def _chain_with(data):
    """A mock supabase query chain whose .execute() returns ``data``."""
    c = MagicMock()
    c.select.return_value = c
    c.eq.return_value = c
    c.maybe_single.return_value = c
    c.execute.return_value = MagicMock(data=data)
    return c


def _mock_db(patient_dnc=None, practitioner_dnc=None):
    """Mock DB whose patients/practitioners lookups return the given do_not_contact."""
    db = MagicMock()
    patient_data = {"do_not_contact": patient_dnc} if patient_dnc else None
    prac_data = {"do_not_contact": practitioner_dnc} if practitioner_dnc else None
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[{"id": "appt-1"}])

    # Cache one chain per table so test assertions inspect the same object the job used.
    patients_chain = _chain_with(patient_data)
    prac_chain = _chain_with(prac_data)

    def table(name):
        if name == "patients":
            return patients_chain
        if name == "practitioners":
            return prac_chain
        if name == "appointments":
            return insert_chain
        return MagicMock()

    db.table.side_effect = table
    db._patients_chain = patients_chain
    db._prac_chain = prac_chain
    return db


@pytest.mark.asyncio
async def test_lapsed_patient_identified():
    """Patients who completed treatment 55-65 days ago without future booking are identified
    using the canonical flat shape (regression for the normalisation-mismatch bug)."""
    from jobs.appointment_followup import identify_lapsed_patients

    client = {
        "id": "client-dental-1",
        "business_name": "Sydney Dental Care",
        "booking_system": "cliniko",
        "cliniko_api_key": "test-key",
    }

    with patch("services.cliniko.get_appointments", new_callable=AsyncMock,
               return_value=[_canonical_appt()]), \
         patch("services.cliniko.get_future_appointments", new_callable=AsyncMock,
               return_value=[]), \
         patch("jobs.appointment_followup._upsert_practitioners", new_callable=AsyncMock):
        lapsed = await identify_lapsed_patients(client)

    assert len(lapsed) == 1
    assert lapsed[0]["patient_id"] == "pat-001"
    assert lapsed[0]["patient_name"] == "John Smith"
    # Canonical key is patient_phone (not the old Cliniko "phone")
    assert lapsed[0]["patient_phone"] == "+61412345678"
    assert lapsed[0]["practitioner_name"] == "Dr Chen"


@pytest.mark.asyncio
async def test_square_canonical_shape_read():
    """The job reads the canonical flat shape for a Square client — proving the
    normalisation-mismatch bug (Square patients came back as name "Patient", no phone)
    is fixed."""
    from jobs.appointment_followup import identify_lapsed_patients

    client = {"id": "c2", "booking_system": "square", "square_access_token": "tok"}
    square_appt = _canonical_appt(
        patient_id="cust-9", patient_name="Jane Roe", patient_phone="+61411112222"
    )
    with patch("services.square_appointments.get_appointments", new_callable=AsyncMock,
               return_value=[square_appt]), \
         patch("services.square_appointments.get_future_appointments", new_callable=AsyncMock,
               return_value=[]), \
         patch("jobs.appointment_followup._upsert_practitioners", new_callable=AsyncMock):
        lapsed = await identify_lapsed_patients(client)

    assert len(lapsed) == 1
    assert lapsed[0]["patient_id"] == "cust-9"
    assert lapsed[0]["patient_name"] == "Jane Roe"
    assert lapsed[0]["patient_phone"] == "+61411112222"


@pytest.mark.asyncio
async def test_unsupported_adapter_returns_empty():
    """A SUPPORTS_REBOOK=False booking system (stub) yields no lapsed patients."""
    from jobs.appointment_followup import identify_lapsed_patients

    client = {"id": "c3", "booking_system": "hotdoc"}
    with patch("services.hotdoc.get_appointments", new_callable=AsyncMock) as mock_get:
        lapsed = await identify_lapsed_patients(client)
    assert lapsed == []
    # The stub is never even called because SUPPORTS_REBOOK short-circuits.
    mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_patient_with_future_booking_not_lapsed():
    """A patient with a future booking is not lapsed."""
    from jobs.appointment_followup import identify_lapsed_patients

    client = {"id": "c4", "booking_system": "cliniko", "cliniko_api_key": "k"}
    with patch("services.cliniko.get_appointments", new_callable=AsyncMock,
               return_value=[_canonical_appt()]), \
         patch("services.cliniko.get_future_appointments", new_callable=AsyncMock,
               return_value=[_canonical_appointment_future()]), \
         patch("jobs.appointment_followup._upsert_practitioners", new_callable=AsyncMock):
        lapsed = await identify_lapsed_patients(client)
    assert lapsed == []


@pytest.mark.asyncio
async def test_id_column_dispatch_uses_adapter_id_column():
    """A nookal client uses nookal_id (adapter.ID_COLUMN) for the patients lookup,
    not the hardcoded cliniko/square id column."""
    from jobs.appointment_followup import _process_lapsed_patient
    from services import nookal as nookal_adapter

    assert nookal_adapter.ID_COLUMN == "nookal_id"

    client = {"id": "cid", "booking_system": "nookal", "business_name": "Clinic", "state": "NSW"}
    db = _mock_db(patient_dnc=False)
    pool = MagicMock()
    pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="job-1"))

    with patch("jobs.appointment_followup.generate_followup_message", new_callable=AsyncMock,
               return_value="Hi"):
        await _process_lapsed_patient(db, client, _canonical_appt(), pool)

    # The patients-chain .eq calls include ("nookal_id", "pat-001").
    patients_calls = db._patients_chain.eq.call_args_list
    assert any(call.args == ("nookal_id", "pat-001") for call in patients_calls)


@pytest.mark.asyncio
async def test_practitioner_do_not_contact_skips_send():
    """Practitioner-level do_not_contact skips the SMS even when patient-level is false."""
    from jobs.appointment_followup import _process_lapsed_patient

    client = {"id": "cid", "booking_system": "cliniko", "business_name": "Clinic", "state": "NSW"}
    # patient_dnc False, practitioner_dnc True
    db = _mock_db(patient_dnc=False, practitioner_dnc=True)
    pool = MagicMock()
    pool.enqueue_job = AsyncMock()

    with patch("jobs.appointment_followup.generate_followup_message", new_callable=AsyncMock) as mock_gen:
        await _process_lapsed_patient(db, client, _canonical_appt(), pool)

    mock_gen.assert_not_awaited()
    pool.enqueue_job.assert_not_awaited()
    # No appointments row written for a skipped patient.
    db.table("appointments").insert.assert_not_called()


@pytest.mark.asyncio
async def test_patient_do_not_contact_skips_send():
    """Patient-level do_not_contact skips the SMS."""
    from jobs.appointment_followup import _process_lapsed_patient

    client = {"id": "cid", "booking_system": "cliniko", "business_name": "Clinic", "state": "NSW"}
    db = _mock_db(patient_dnc=True)
    pool = MagicMock()
    pool.enqueue_job = AsyncMock()

    with patch("jobs.appointment_followup.generate_followup_message", new_callable=AsyncMock) as mock_gen:
        await _process_lapsed_patient(db, client, _canonical_appt(), pool)

    mock_gen.assert_not_awaited()
    pool.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_type_threaded_into_message_and_insert():
    """claim_type is threaded into generate_followup_message and written to appointments."""
    from jobs.appointment_followup import _process_lapsed_patient

    client = {"id": "cid", "booking_system": "cliniko", "business_name": "Clinic", "state": "NSW"}
    db = _mock_db(patient_dnc=False)
    pool = MagicMock()
    pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="job-1"))
    appt = _canonical_appt(claim={"type": "bulk_billed", "fund": "Medicare", "gap_amount": None})

    with patch("jobs.appointment_followup.generate_followup_message", new_callable=AsyncMock,
               return_value="Msg") as mock_gen:
        await _process_lapsed_patient(db, client, appt, pool)

    _, kwargs = mock_gen.call_args
    assert kwargs["claim_type"] == "bulk_billed"
    assert kwargs["practitioner_name"] == "Dr Chen"

    insert_data = db.table("appointments").insert.call_args.args[0]
    assert insert_data["claim_type"] == "bulk_billed"
    assert insert_data["claim_fund"] == "Medicare"
    assert insert_data["practitioner_name"] == "Dr Chen"
    assert insert_data["followup_message"] == "Msg"


@pytest.mark.asyncio
async def test_sms_enqueued_via_arq_not_direct():
    """Outbound SMS routes through the durable send_sms_task arq enqueue (C4), not a
    direct twilio_sms.send_sms call."""
    from jobs.appointment_followup import _process_lapsed_patient

    client = {"id": "cid", "booking_system": "cliniko", "business_name": "Clinic", "state": "VIC"}
    db = _mock_db(patient_dnc=False)
    pool = MagicMock()
    pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="SM-job-1"))

    with patch("jobs.appointment_followup.generate_followup_message", new_callable=AsyncMock,
               return_value="Hello"), \
         patch("services.twilio_sms.send_sms", new_callable=AsyncMock) as mock_direct:
        await _process_lapsed_patient(db, client, _canonical_appt(), pool)

    mock_direct.assert_not_awaited()
    pool.enqueue_job.assert_awaited_once()
    assert pool.enqueue_job.call_args.args[0] == "send_sms_task"
    # (to, body, state) forwarded positionally
    assert pool.enqueue_job.call_args.args[1] == "+61412345678"
    assert pool.enqueue_job.call_args.args[2] == "Hello"
    assert pool.enqueue_job.call_args.args[3] == "VIC"

    insert_data = db.table("appointments").insert.call_args.args[0]
    assert insert_data["followup_sid"] == "SM-job-1"
    assert insert_data["followup_sent"] is True


@pytest.mark.asyncio
async def test_no_phone_skips_sms():
    """A patient without a phone number is skipped (no enqueue, no insert)."""
    from jobs.appointment_followup import _process_lapsed_patient

    client = {"id": "cid", "booking_system": "cliniko", "business_name": "Clinic", "state": "NSW"}
    db = _mock_db(patient_dnc=False)
    pool = MagicMock()
    pool.enqueue_job = AsyncMock()
    appt = _canonical_appt(patient_phone=None)

    with patch("jobs.appointment_followup.generate_followup_message", new_callable=AsyncMock,
               return_value="Hi"):
        await _process_lapsed_patient(db, client, appt, pool)

    pool.enqueue_job.assert_not_awaited()
    db.table("appointments").insert.assert_not_called()


@pytest.mark.asyncio
async def test_practitioner_upsert_dedups_per_external_id():
    """_upsert_practitioners upserts one row per unique practitioner external_id."""
    from jobs.appointment_followup import _upsert_practitioners

    db = MagicMock()
    upsert_chain = MagicMock()
    db.table.return_value = upsert_chain

    appointments = [
        _canonical_appt(practitioner_id="prac-01", practitioner_name="Dr Chen"),
        _canonical_appt(practitioner_id="prac-01", practitioner_name="Dr Chen"),  # dup
        _canonical_appt(practitioner_id="prac-02", practitioner_name="Dr Lee"),
        _canonical_appt(practitioner_id=None, practitioner_name=None),  # no practitioner
    ]
    await _upsert_practitioners(db, "cid", "cliniko", appointments)

    assert upsert_chain.upsert.call_count == 2
    upserted = {c.args[0]["external_id"]: c.args[0]["name"] for c in upsert_chain.upsert.call_args_list}
    assert upserted == {"prac-01": "Dr Chen", "prac-02": "Dr Lee"}
    for c in upsert_chain.upsert.call_args_list:
        assert c.args[0]["booking_system"] == "cliniko"
        assert c.args[0]["client_id"] == "cid"
        assert c.kwargs["on_conflict"] == "client_id,booking_system,external_id"


def test_au_holiday_skips_send():
    """AU public holidays are correctly identified for SMS skip logic."""
    from jobs.appointment_followup import is_au_public_holiday

    assert is_au_public_holiday(date(2026, 1, 1), "NSW") is True
    assert is_au_public_holiday(date(2026, 7, 17), "NSW") is False


@pytest.mark.asyncio
async def test_run_all_writes_adapter_unsupported_marker():
    """A client whose booking system is a stub gets an appointments marker row with
    followup_error='adapter_unsupported' and is skipped (no identify call)."""
    from jobs.appointment_followup import run_appointment_followup_all_clients

    db = MagicMock()
    clients_chain = _chain_with([{
        "id": "c1",
        "booking_system": "hotdoc",
        "active_jobs": ["appointment_followup"],
    }])
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[{}])

    def table(name):
        if name == "clients":
            return clients_chain
        if name == "appointments":
            return insert_chain
        return MagicMock()

    db.table.side_effect = table

    with patch("jobs.appointment_followup.get_db", return_value=db), \
         patch("services.hotdoc.get_appointments", new_callable=AsyncMock) as mock_get:
        await run_appointment_followup_all_clients(arq_pool=None)

    # Marker row written; stub adapter never queried for appointments.
    insert_data = insert_chain.insert.call_args.args[0]
    assert insert_data["followup_error"] == "adapter_unsupported"
    assert insert_data["client_id"] == "c1"
    mock_get.assert_not_awaited()
