import logging
from fastapi import APIRouter, Depends, HTTPException
from db import get_db
from middleware.auth import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/review/{draft_id}")
async def approve_review(draft_id: str, edited_text: str | None = None, auth: dict = Depends(require_auth)):
    """Approve a draft and post the reply to GBP. If edited_text is provided, post that instead."""
    db = get_db()
    draft_resp = db.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not draft_resp.data:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft = draft_resp.data
    if draft["status"] != "pending_approval":
        raise HTTPException(status_code=409, detail="Draft already actioned")

    reply_text = edited_text if edited_text else draft["draft_text"]

    client_resp = db.table("clients").select("gbp_access_token, gbp_location_id").eq("id", draft["client_id"]).single().execute()
    if not client_resp.data:
        raise HTTPException(status_code=404, detail="Client not found")

    client = client_resp.data
    access_token = client.get("gbp_access_token")
    location_id = client.get("gbp_location_id")

    posted = False
    if access_token and location_id and draft.get("source_id"):
        try:
            from services.gbp import post_review_reply
            posted = await post_review_reply(location_id, draft["source_id"], reply_text, access_token)
        except Exception as e:
            logger.error(f"GBP post failed for draft {draft_id}: {e}")

    db.table("drafts").update({
        "status": "posted" if posted else "approved",
        "draft_text": reply_text if edited_text else draft["draft_text"],
        "actioned_at": "now()"
    }).eq("id", draft_id).execute()

    return {"status": "posted" if posted else "approved", "draft_id": draft_id}


@router.delete("/review/{draft_id}")
async def discard_review(draft_id: str, auth: dict = Depends(require_auth)):
    """Discard a draft — no reply is posted to GBP."""
    db = get_db()
    draft_resp = db.table("drafts").select("status").eq("id", draft_id).single().execute()
    if not draft_resp.data:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft_resp.data["status"] != "pending_approval":
        raise HTTPException(status_code=409, detail="Draft already actioned")

    db.table("drafts").update({"status": "discarded", "actioned_at": "now()"}).eq("id", draft_id).execute()
    return {"status": "discarded", "draft_id": draft_id}
