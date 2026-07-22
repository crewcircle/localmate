"""Canonical normalised appointment shape shared by all booking adapters.

Every adapter's ``get_appointments`` / ``get_future_appointments`` returns a list of
dicts produced by :func:`canonical_appointment`, so the daily Rebook job reads ONE
agreed shape regardless of PMS. This fixes the normalisation-mismatch bug where the
job read Cliniko-shaped raw keys (``appt["patient"]["id"]``) while Square returned a
flat dict (``patient_id``) — so Square patients came back with name "Patient", no
phone and wrong treatment/date fields.

Canonical keys (extends the Square flat shape with practitioner + claim):

    patient_id, patient_name, patient_phone, patient_email, treatment_type,
    appointment_date, status, practitioner_id, practitioner_name, claim (dict|None)

``claim`` (best-effort, PMS-sourced — D3-A keeps it OUT of SMS copy):
    {"type": "bulk_billed"|"gap"|"private_health"|"unknown",
     "fund": str|None, "gap_amount": float|None}
"""


def canonical_appointment(
    *,
    patient_id,
    patient_name,
    patient_phone=None,
    patient_email=None,
    treatment_type="",
    appointment_date="",
    status="completed",
    practitioner_id=None,
    practitioner_name=None,
    claim=None,
) -> dict:
    """Build a normalised appointment dict with exactly the canonical keys."""
    return {
        "patient_id": str(patient_id) if patient_id is not None and patient_id != "" else "",
        "patient_name": patient_name or "Patient",
        "patient_phone": patient_phone,
        "patient_email": patient_email,
        "treatment_type": treatment_type or "",
        "appointment_date": appointment_date or "",
        "status": status or "completed",
        "practitioner_id": str(practitioner_id) if practitioner_id else None,
        "practitioner_name": practitioner_name,
        "claim": claim,
    }


def make_claim(claim_type=None, fund=None, gap_amount=None) -> dict | None:
    """Build a best-effort claim dict, or ``None`` when no claim data is available."""
    if not claim_type and not fund and gap_amount is None:
        return None
    return {
        "type": claim_type or "unknown",
        "fund": fund,
        "gap_amount": gap_amount,
    }
