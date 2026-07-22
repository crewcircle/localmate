import base64
import hashlib
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
import stripe
from db import get_db
from config import settings

router = APIRouter()
logger = logging.getLogger(__name__)
stripe.api_key = settings.stripe_secret_key


# ---------------------------------------------------------------------------
# Durable persistence helpers
# ---------------------------------------------------------------------------

def _persist_event(provider: str, idempotency_key: str, event_type: str | None, payload: dict) -> dict:
    """Insert a webhook_events row (status='pending'). Returns
    ``{"status": "persisted", "event_id": id}`` or ``{"status": "duplicate"}``
    when the (provider, idempotency_key) already exists.
    """
    db = get_db()
    existing = (
        db.table("webhook_events")
        .select("id, status")
        .eq("provider", provider)
        .eq("idempotency_key", idempotency_key)
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        return {"status": "duplicate", "event_id": existing.data["id"]}

    try:
        resp = (
            db.table("webhook_events")
            .insert(
                {
                    "provider": provider,
                    "idempotency_key": idempotency_key,
                    "event_type": event_type,
                    "payload": payload,
                    "status": "pending",
                }
            )
            .execute()
        )
    except Exception as e:
        # Unique-constraint race → treat as duplicate rather than 500.
        logger.info("webhook_events insert conflict for %s/%s: %s", provider, idempotency_key, e)
        return {"status": "duplicate"}

    event_id = resp.data[0]["id"] if resp.data else None
    return {"status": "persisted", "event_id": event_id}


async def _enqueue(request: Request, task: str, event_id: str) -> None:
    """Enqueue a processing task on the app's arq pool. On failure the row stays
    'pending' and the reconciler re-enqueues it (Redis-briefly-down edge case)."""
    arq = getattr(request.app.state, "arq", None)
    if arq is None:
        logger.warning("arq pool unavailable — leaving event %s pending for reconcile", event_id)
        return
    try:
        await arq.enqueue_job(task, event_id)
    except Exception as e:
        logger.error("enqueue %s(%s) failed — left pending for reconcile: %s", task, event_id, e)


# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------

@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Persist + enqueue Stripe webhook events. Returns 200 fast."""
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(body, sig, settings.stripe_webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = dict(event)
    result = _persist_event("stripe", event["id"], event.get("type"), payload)
    if result["status"] == "duplicate":
        return {"status": "duplicate"}

    await _enqueue(request, "process_stripe_event", result["event_id"])
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


# ---------------------------------------------------------------------------
# Google Business Profile inbound review (Pub/Sub push)
# ---------------------------------------------------------------------------

def decode_pubsub_envelope(envelope: dict) -> dict:
    """Decode a Cloud Pub/Sub push envelope.

    Standard shape::

        {"message": {"data": "<base64>", "messageId": "...", ...}, "subscription": "..."}

    Returns ``{"message_id": str, "notification": dict}`` where ``notification``
    is the decoded GBP notification (e.g. ``{"notificationType": "NEW_REVIEW",
    "location": "...", "review": "..."}``). Raises ValueError on a malformed
    envelope.
    """
    message = envelope.get("message")
    if not isinstance(message, dict):
        raise ValueError("missing Pub/Sub message")
    message_id = message.get("messageId") or message.get("message_id")
    if not message_id:
        raise ValueError("missing Pub/Sub messageId")
    data_b64 = message.get("data")
    notification: dict = {}
    if data_b64:
        try:
            decoded = base64.b64decode(data_b64).decode("utf-8")
            notification = json.loads(decoded) if decoded else {}
        except Exception as e:
            raise ValueError(f"invalid Pub/Sub message.data: {e}")
    return {"message_id": message_id, "notification": notification}


async def fetch_review_resource(review_name: str) -> dict:
    """Fetch a GBP review resource by its full resource name.

    ``review_name`` is ``accounts/{a}/locations/{l}/reviews/{r}``. Resolves the
    owning client's access token and GETs the review via the GBP reviews API.
    Returns the review resource dict (empty dict when unavailable).
    """
    import httpx
    from services.gbp import GBP_REVIEWS_BASE, refresh_access_token

    client = resolve_client_from_location(review_name)
    if not client:
        logger.warning("fetch_review_resource: no client for %s", review_name)
        return {}

    access_token = client.get("gbp_access_token", "")
    refresh_token = client.get("gbp_refresh_token", "")
    if not access_token and refresh_token:
        try:
            access_token = await refresh_access_token(refresh_token)
        except Exception as e:
            logger.error("fetch_review_resource: token refresh failed: %s", e)
            return {}

    url = f"{GBP_REVIEWS_BASE}/{review_name}"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error("fetch_review_resource GET failed for %s: %s", review_name, e)
        return {}


@router.post("/inbound-review")
async def inbound_review(request: Request):
    """GBP review notification (Pub/Sub push). Decode envelope, dedupe by
    messageId, fetch the review resource, persist + enqueue. Returns 200 fast."""
    envelope = await request.json()
    try:
        decoded = decode_pubsub_envelope(envelope)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid Pub/Sub envelope: {e}")

    message_id = decoded["message_id"]
    notification = decoded["notification"]

    # The notification identifies the review resource (accounts/.../reviews/{id}).
    review_name = (
        notification.get("review")
        or notification.get("name")
        or notification.get("reviewName", "")
    )

    review = await fetch_review_resource(review_name) if review_name else {}
    # Build the payload the process_review task consumes. Prefer the fetched
    # resource; fall back to the notification fields.
    payload = dict(review) if review else {}
    payload.setdefault("name", review.get("name") or review_name)
    if notification.get("notificationType"):
        payload["notificationType"] = notification["notificationType"]

    result = _persist_event("gbp", message_id, notification.get("notificationType"), payload)
    if result["status"] == "duplicate":
        return {"status": "duplicate"}

    await _enqueue(request, "process_gbp_review", result["event_id"])
    return {"status": "received"}


async def process_review(payload: dict):
    """Create Claude draft for a new review. Called by the process_gbp_review task."""
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


# ---------------------------------------------------------------------------
# Menu update (Google Sheets webhook)
# ---------------------------------------------------------------------------

@router.post("/menu-update/{client_id}")
async def menu_update(client_id: str, payload: dict, request: Request):
    """Persist + enqueue a Google Sheets menu change. Returns 200 fast.

    item = {name, price_cents=int(float(price)*100), description, category, active}.
    """
    item = {
        "name": payload.get("name"),
        "price_cents": int(float(payload.get("price", 0)) * 100),
        "description": payload.get("description", ""),
        "category": payload.get("category", ""),
        "active": payload.get("active", True),
    }
    # Synthetic idempotency key: client + item name + minute bucket.
    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    raw = f"{client_id}:{item['name']}:{bucket}"
    idempotency_key = hashlib.sha256(raw.encode()).hexdigest()

    result = _persist_event(
        "menu", idempotency_key, "menu-update", {"client_id": client_id, "item": item}
    )
    if result["status"] == "duplicate":
        return {"status": "duplicate"}

    await _enqueue(request, "process_menu_update", result["event_id"])
    return {"status": "received"}
