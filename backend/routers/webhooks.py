import logging
from fastapi import APIRouter, Request, HTTPException
import stripe
from db import get_db
from config import settings

router = APIRouter()
logger = logging.getLogger(__name__)
stripe.api_key = settings.stripe_secret_key


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(body, sig, settings.stripe_webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "customer.subscription.trial_will_end":
        await handle_trial_will_end(data)
    elif event_type == "customer.subscription.updated":
        if data.get("status") == "active":
            await activate_client_by_subscription(data["id"])
    elif event_type == "customer.subscription.deleted":
        await expire_client_by_subscription(data["id"])
    elif event_type == "invoice.payment_failed":
        await pause_client_jobs_by_subscription(data.get("subscription"))
    else:
        logger.info(f"Unhandled Stripe event: {event_type}")

    return {"status": "received"}


async def handle_trial_will_end(sub: dict):
    """Stripe sends this 3 days before trial ends — backup for day-12 email."""
    customer_id = sub.get("customer")
    db = get_db()
    resp = db.table("clients").select("id, email, business_name").eq("stripe_customer_id", customer_id).single().execute()
    if not resp.data:
        return
    try:
        from services.resend_email import send_trial_day12_email
        await send_trial_day12_email(resp.data["email"], resp.data["business_name"], resp.data["id"])
    except Exception as e:
        logger.error(f"trial_will_end email failed: {e}")


async def activate_client_by_subscription(subscription_id: str):
    """Subscription became active — full access."""
    db = get_db()
    db.table("clients").update({"subscription_status": "active"}).eq("stripe_subscription_id", subscription_id).execute()


async def expire_client_by_subscription(subscription_id: str):
    """Subscription deleted — expire client."""
    db = get_db()
    db.table("clients").update({
        "subscription_status": "cancelled",
        "trial_status": "expired"
    }).eq("stripe_subscription_id", subscription_id).execute()


async def pause_client_jobs_by_subscription(subscription_id: str | None):
    """Payment failed — pause jobs but keep data."""
    if not subscription_id:
        return
    db = get_db()
    db.table("clients").update({"subscription_status": "past_due"}).eq("stripe_subscription_id", subscription_id).execute()


@router.post("/inbound-review")
async def inbound_review(request: Request):
    """Google Business Profile webhook — new review posted."""
    payload = await request.json()
    try:
        await process_review(payload)
    except Exception as e:
        logger.error(f"process_review failed: {e}")
        raise HTTPException(status_code=500, detail="Review processing failed")
    return {"status": "processing"}


async def process_review(payload: dict):
    """Create Claude draft for a new review. GBP webhook calls this."""
    name = payload.get("name", "")
    review_text = payload.get("comment", "")
    rating = payload.get("starRating", 5)
    reviewer = payload.get("reviewer", {}).get("displayName", "Reviewer")

    client = resolve_client_from_location(name)
    if not client:
        logger.warning(f"No client found for GBP location: {name}")
        return

    from middleware.trial_gate import check_trial_gate, increment_trial_usage
    gate = await check_trial_gate(client["id"], "review_drafts")
    if not gate["allowed"]:
        logger.info(f"Trial gate blocked review for {client['id']}: {gate['reason']}")
        return

    try:
        from services.claude import generate_review_response
        voice = client.get("voice_sample", "")
        draft_text = await generate_review_response(
            review_text=review_text,
            rating=rating,
            reviewer_name=reviewer,
            voice_sample=voice
        )
    except ImportError:
        logger.warning("claude.py not yet implemented — skipping draft generation")
        return
    except Exception as e:
        logger.error(f"Claude draft generation failed: {e}")
        return

    review_id = name.split("/")[-1] if name else ""
    db = get_db()
    db.table("drafts").insert({
        "client_id": client["id"],
        "job": "review_response",
        "source_id": review_id,
        "source": "google",
        "draft_text": draft_text,
        "status": "pending_approval",
        "metadata": payload
    }).execute()

    await increment_trial_usage(client["id"], "review_drafts")


def resolve_client_from_location(gbp_name: str) -> dict | None:
    """Map GBP `accounts/{accountId}/locations/{locationId}/reviews/{reviewId}` to client."""
    db = get_db()
    parts = gbp_name.split("/")
    location_id = None
    for i, part in enumerate(parts):
        if part == "locations" and i + 1 < len(parts):
            location_id = parts[i + 1]
            break
    if not location_id:
        return None
    resp = db.table("clients").select("*").eq("gbp_location_id", location_id).maybe_single().execute()
    return resp.data if resp.data else None


@router.post("/menu-update/{client_id}")
async def menu_update(client_id: str, payload: dict):
    """Webhook for Google Sheets menu changes. Payload is changed row.
    item = {name, price_cents=int(float(price)*100), description, category, active}.
    Syncs to all platforms in client.menu_sync_targets via asyncio.gather."""
    from jobs.menu_sync import sync_menu_item
    item = {
        "name": payload.get("name"),
        "price_cents": int(float(payload.get("price", 0)) * 100),
        "description": payload.get("description", ""),
        "category": payload.get("category", ""),
        "active": payload.get("active", True),
    }
    result = await sync_menu_item(client_id, item)
    return result
