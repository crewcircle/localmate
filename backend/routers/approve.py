import logging
from fastapi import APIRouter, Depends, HTTPException
from db import get_db
from middleware.auth import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/review/{draft_id}")
async def approve_review(draft_id: str, edited_text: str | None = None, auth: dict = Depends(require_auth)):
    """Approve a draft and post the reply.

    Branches on ``draft["source"]``:
    - ``source == "google"`` → post the reply to GBP via the existing path
      (uses the draft's location's ``gbp_location_id`` per C2).
    - ``source == "yelp"`` → Yelp has no reply-write API, so set status to
      ``awaiting_manual_post``, store the Yelp review deep link in
      ``drafts.external_action_url``, and return the reply text for the owner
      to paste manually.
    """
    db = get_db()
    draft_resp = db.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not draft_resp.data:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft = draft_resp.data
    if draft["status"] != "pending_approval":
        raise HTTPException(status_code=409, detail="Draft already actioned")

    reply_text = edited_text if edited_text else draft["draft_text"]
    source = draft.get("source", "google")

    # ------------------------------------------------------------------
    # Yelp: guided manual posting (no reply-write API exists)
    # ------------------------------------------------------------------
    if source == "yelp":
        metadata = draft.get("metadata") or {}
        yelp_url = metadata.get("url", "")

        db.table("drafts").update({
            "status": "awaiting_manual_post",
            "draft_text": reply_text if edited_text else draft["draft_text"],
            "external_action_url": yelp_url,
            "actioned_at": "now()"
        }).eq("id", draft_id).execute()

        return {
            "status": "awaiting_manual_post",
            "draft_id": draft_id,
            "yelp_url": yelp_url,
            "reply_text": reply_text,
        }

    # ------------------------------------------------------------------
    # Google: existing GBP post path (unchanged, uses location's gbp_location_id per C2)
    # ------------------------------------------------------------------
    client_resp = db.table("clients").select("gbp_access_token").eq("id", draft["client_id"]).single().execute()
    if not client_resp.data:
        raise HTTPException(status_code=404, detail="Client not found")

    access_token = client_resp.data.get("gbp_access_token")

    # C2: resolve GBP location path from draft's location_id (locations table)
    gbp_location_path = None
    draft_location_id = draft.get("location_id")
    if draft_location_id:
        loc_resp = (
            db.table("locations")
            .select("gbp_account_id, gbp_location_id")
            .eq("id", draft_location_id)
            .maybe_single()
            .execute()
        )
        if loc_resp.data:
            acct = loc_resp.data.get("gbp_account_id")
            loc = loc_resp.data.get("gbp_location_id")
            if acct and loc:
                gbp_location_path = f"accounts/{acct}/locations/{loc}"

    posted = False
    if access_token and gbp_location_path and draft.get("source_id"):
        try:
            from services.gbp import post_review_reply
            posted = await post_review_reply(gbp_location_path, draft["source_id"], reply_text, access_token)
        except Exception as e:
            logger.error(f"GBP post failed for draft {draft_id}: {e}")

    db.table("drafts").update({
        "status": "posted" if posted else "approved",
        "draft_text": reply_text if edited_text else draft["draft_text"],
        "actioned_at": "now()"
    }).eq("id", draft_id).execute()

    return {"status": "posted" if posted else "approved", "draft_id": draft_id}


@router.post("/review/{draft_id}/mark-posted")
async def mark_review_posted(draft_id: str, auth: dict = Depends(require_auth)):
    """Owner confirms they pasted the reply on Yelp.

    Transitions ``awaiting_manual_post`` → ``posted``. This is an owner-attested
    state — Yelp has no reply-write API to verify the post programmatically.
    """
    db = get_db()
    draft_resp = db.table("drafts").select("status").eq("id", draft_id).single().execute()
    if not draft_resp.data:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft_resp.data["status"] != "awaiting_manual_post":
        raise HTTPException(status_code=409, detail="Draft is not awaiting manual post")

    db.table("drafts").update({"status": "posted", "actioned_at": "now()"}).eq("id", draft_id).execute()
    return {"status": "posted", "draft_id": draft_id}


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
