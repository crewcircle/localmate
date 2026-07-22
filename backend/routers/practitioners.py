"""Practitioners read + opt-out API (Phase 2 — Clinical, read API for Phase 5).

``GET /practitioners`` lists a client's practitioners (incl. ``do_not_contact``).
``PATCH /practitioners/{id}`` toggles the per-practitioner opt-out so a clinic can
suppress follow-ups routed to a specific clinician.

Tenant scoping: this phase runs standalone (the Phase 1 tenant-auth binding is on a
separate branch), so ``client_id`` is accepted as a query/body param and the
standard ``Depends(require_auth)`` guards the endpoint. The practitioner update is
additionally scoped to the supplied ``client_id`` so an id from another tenant
cannot be mutated.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from db import get_db
from middleware.auth import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def list_practitioners(
    client_id: str = Query(..., description="Client whose practitioners to list"),
    auth: dict = Depends(require_auth),
):
    """List practitioners for a client, including opt-out state."""
    db = get_db()
    resp = (
        db.table("practitioners")
        .select("*")
        .eq("client_id", client_id)
        .order_by("name")
        .execute()
    )
    return {"practitioners": resp.data or []}


@router.patch("/{practitioner_id}")
async def update_practitioner(
    practitioner_id: str,
    payload: dict,
    client_id: str = Query(..., description="Client that owns the practitioner"),
    auth: dict = Depends(require_auth),
):
    """Update a practitioner — currently supports the opt-out toggle.

    Accepts ``{"do_not_contact": bool}``. Scoped to ``client_id`` so a practitioner
    id from another tenant cannot be mutated.
    """
    if "do_not_contact" not in payload:
        raise HTTPException(status_code=422, detail="Missing field: do_not_contact")

    db = get_db()
    resp = (
        db.table("practitioners")
        .update({"do_not_contact": bool(payload["do_not_contact"])})
        .eq("id", practitioner_id)
        .eq("client_id", client_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Practitioner not found")
    return {"practitioner": resp.data[0]}
