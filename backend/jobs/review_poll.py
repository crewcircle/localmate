import logging
import httpx
from db import get_db
from config import settings
from utils.retry import retry_on_failure

logger = logging.getLogger(__name__)

YELP_FUSION_BASE = "https://api.yelp.com/v3"


async def poll_yelp_reviews_all_clients() -> None:
    """APScheduler job — poll Yelp for new reviews every 24h for all clients with yelp_business_id."""
    db = get_db()
    resp = db.table("clients").select("id, business_name, voice_sample, yelp_business_id").not_.is_("yelp_business_id", "null").execute()
    if not resp.data:
        return

    for client in resp.data:
        yelp_id = client["yelp_business_id"]
        if not yelp_id:
            continue
        try:
            new_reviews = await _fetch_yelp_reviews(yelp_id)
            for review in new_reviews:
                await _create_yelp_draft(client, review)
        except Exception as e:
            logger.error(f"Yelp poll failed for {client['id']}: {e}")


@retry_on_failure()
async def _fetch_yelp_reviews(yelp_business_id: str) -> list[dict]:
    """Fetch reviews from Yelp Fusion API."""
    yelp_key = getattr(settings, "yelp_api_key", None)
    if not yelp_key:
        logger.warning("Yelp API key not configured — skipping Yelp poll")
        return []

    headers = {"Authorization": f"Bearer {yelp_key}"}
    url = f"{YELP_FUSION_BASE}/businesses/{yelp_business_id}/reviews"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("reviews", [])


@retry_on_failure()
async def _generate_review_draft(
    review_text: str,
    rating: int,
    reviewer_name: str,
    voice_sample: str,
) -> str:
    from services.claude import generate_review_response

    return await generate_review_response(
        review_text=review_text,
        rating=rating,
        reviewer_name=reviewer_name,
        voice_sample=voice_sample,
    )


async def _create_yelp_draft(client: dict, review: dict) -> None:
    """Create a Claude draft for a new Yelp review."""
    review_id = review.get("id", "")
    db = get_db()

    existing = db.table("drafts").select("id").eq("source_id", review_id).eq("source", "yelp").execute()
    if existing.data:
        return

    from middleware.trial_gate import check_trial_gate, increment_trial_usage
    gate = await check_trial_gate(client["id"], "review_drafts")
    if not gate["allowed"]:
        logger.info(f"Trial gate blocked Yelp review for {client['id']}: {gate['reason']}")
        return

    draft_text = await _generate_review_draft(
        review_text=review.get("text", ""),
        rating=review.get("rating", 5),
        reviewer_name=review.get("user", {}).get("name", "Reviewer"),
        voice_sample=client.get("voice_sample", ""),
    )

    db.table("drafts").insert({
        "client_id": client["id"],
        "job": "review_response",
        "source_id": review_id,
        "source": "yelp",
        "draft_text": draft_text,
        "status": "pending_approval",
        "metadata": review
    }).execute()

    await increment_trial_usage(client["id"], "review_drafts")
