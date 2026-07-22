"""SEO read APIs for Phase 5 dashboard (C7).

Tenant-scoped endpoints that derive ``client_id`` from a location_id query
param (the location belongs to exactly one client). Both organic + map rank
and competitor structured diffs are surfaced.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from db import get_db
from middleware.auth import require_auth

router = APIRouter()


def _resolve_client_id_from_location(db, location_id: str) -> str:
    """Resolve client_id from a location row. Raises 404 if not found."""
    resp = (
        db.table("locations")
        .select("client_id")
        .eq("id", location_id)
        .maybe_single()
        .execute()
    )
    if not resp or not resp.data:
        raise HTTPException(status_code=404, detail="Location not found")
    return resp.data["client_id"]


@router.get("/rankings")
async def get_rankings(
    location_id: str = Query(...),
    auth: dict = Depends(require_auth),
):
    """Get weekly ranking snapshots for a location's client.

    Returns organic (``position``) + Maps (``map_position``) rank per keyword
    per week, ordered most-recent-first.
    """
    db = get_db()
    client_id = _resolve_client_id_from_location(db, location_id)

    resp = (
        db.table("rankings")
        .select("keyword, position, map_position, url, week_start")
        .eq("client_id", client_id)
        .order("week_start", desc=True)
        .order("keyword")
        .execute()
    )
    return {"rankings": resp.data or []}


@router.get("/competitors/snapshots")
async def get_competitor_snapshots(
    location_id: str = Query(...),
    auth: dict = Depends(require_auth),
):
    """Get competitor snapshots with structured diffs for a location's client.

    Per C8, ``client_id`` is derived from the ``location_id`` lookup (the
    location belongs to exactly one client) — never accepted directly from
    the query string.

    Returns the most recent snapshots (with ``structured_data`` and
    ``structured_diff``) for the Phase 5 competitor structured-diffs view.
    """
    db = get_db()
    client_id = _resolve_client_id_from_location(db, location_id)

    resp = (
        db.table("competitor_snapshots")
        .select(
            "id, competitor_url, content_hash, brief_text, threat_level, "
            "structured_data, structured_diff, captured_at"
        )
        .eq("client_id", client_id)
        .order("captured_at", desc=True)
        .limit(50)
        .execute()
    )
    return {"snapshots": resp.data or []}
