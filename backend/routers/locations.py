"""Locations management API (Phase 3 — C7 read/write for Phase 5).

Uses ``client_id`` as a query param since Phase 1 tenant-auth binding is not
merged yet. Once C8 lands, ``client_id`` will be derived from the authenticated
identity.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from db import get_db
from middleware.auth import require_auth

router = APIRouter()


@router.get("")
async def list_locations(
    client_id: str = Query(...),
    auth: dict = Depends(require_auth),
):
    """List all locations for a client."""
    db = get_db()
    resp = (
        db.table("locations")
        .select("*")
        .eq("client_id", client_id)
        .is_("deleted_at", "null")
        .order("is_default", desc=True)
        .execute()
    )
    return {"locations": resp.data}


@router.post("")
async def create_location(payload: dict, auth: dict = Depends(require_auth)):
    """Create a new location for a client."""
    required = ["client_id", "name"]
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=422, detail=f"Missing field: {field}")

    db = get_db()
    row = {
        "client_id": payload["client_id"],
        "name": payload["name"],
        "suburb": payload.get("suburb"),
        "state": payload.get("state"),
        "gbp_account_id": payload.get("gbp_account_id"),
        "gbp_location_id": payload.get("gbp_location_id"),
        "square_location_id": payload.get("square_location_id"),
        "place_id": payload.get("place_id"),
        "menu_sync_targets": payload.get("menu_sync_targets", []),
        "is_default": payload.get("is_default", False),
    }
    resp = db.table("locations").insert(row).execute()
    return {"location": resp.data[0] if resp.data else {}}


@router.patch("/{location_id}")
async def update_location(
    location_id: str, payload: dict, auth: dict = Depends(require_auth)
):
    """Update a location (target toggles, Square pairing, etc.)."""
    db = get_db()
    allowed = {
        "name", "suburb", "state", "gbp_account_id", "gbp_location_id",
        "square_location_id", "place_id", "menu_sync_targets", "is_default",
    }
    update = {k: v for k, v in payload.items() if k in allowed}
    if not update:
        raise HTTPException(status_code=422, detail="No valid fields to update")

    resp = (
        db.table("locations")
        .update(update)
        .eq("id", location_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Location not found")
    return {"location": resp.data[0]}
