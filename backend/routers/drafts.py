from fastapi import APIRouter, Depends, Query
from db import get_db
from middleware.auth import require_auth

router = APIRouter()


@router.get("")
async def list_drafts(
    status: str = Query(default="pending_approval"),
    client_id: str | None = Query(default=None),
    auth: dict = Depends(require_auth),
):
    """List drafts for dashboard approval queue."""
    db = get_db()
    query = db.table("drafts").select("*").eq("status", status).order("created_at", desc=True)
    if client_id:
        query = query.eq("client_id", client_id)
    resp = query.execute()
    return {"drafts": resp.data}
