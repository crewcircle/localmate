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
from datetime import datetime


def parse_iso_date(value: str | None) -> str:
    """Extract YYYY-MM-DD from an ISO date/datetime string, or return ``""``.

    Shared by all adapters that previously carried a private ``_parse_date``.
    Nookal's plain ``"YYYY-MM-DD"`` fallback (some PMS APIs return bare dates)
    fires only in the except branch, so it is harmless for other adapters.
    """
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except (ValueError, TypeError):
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]
        return ""


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


def extract_claim_from_billing(item: dict) -> dict | None:
    """Best-effort claim extraction from a PMS billing/invoice block, else ``None``.

    Shared by adapters (Nookal, Cliniko) that surface a ``billing`` or
    ``invoice`` sub-dict on appointment payloads.
    """
    billing = item.get("billing") or item.get("invoice") or {}
    if not isinstance(billing, dict) or not billing:
        return None
    return make_claim(
        claim_type=billing.get("claim_type") or billing.get("type"),
        fund=billing.get("fund") or billing.get("health_fund"),
        gap_amount=billing.get("gap_amount"),
    )
