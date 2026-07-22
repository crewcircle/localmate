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

def _is_unique_violation(exc: Exception) -> bool:
    """True only for a Postgres unique-violation (SQLSTATE 23505).

    supabase-py raises ``postgrest.exceptions.APIError`` whose ``code`` carries
    the SQLSTATE. Only a genuine duplicate key is a benign duplicate; every other
    persistence error (outage, permission, malformed payload, missing migration)
    must propagate so the provider retries rather than getting a false 200.
    """
    code = getattr(exc, "code", None)
    if code == "23505":
        return True
    # Fallback for error shapes that stash the code in args/message.
    text = str(getattr(exc, "message", "") or exc)
    return "23505" in text or "duplicate key value" in text


def _persist_event(provider: str, idempotency_key: str, event_type: str | None, payload: dict) -> dict:
    """Insert a webhook_events row (status='pending'). Returns
    ``{"status": "persisted", "event_id": id}`` or ``{"status": "duplicate"}``
    when the (provider, idempotency_key) already exists.

    Raises on any persistence error that is NOT a unique-violation, so the
    provider retries instead of receiving a false 200 with no durable row.
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
        # Only a unique-constraint race is a benign duplicate. Everything else
        # (DB outage, permission, bad payload, missing migration) must NOT be
        # acked as duplicate — re-raise so the provider retries.
        if _is_unique_violation(e):
            logger.info("webhook_events insert conflict for %s/%s (dedup)", provider, idempotency_key)
            return {"status": "duplicate"}
        logger.error("webhook_events insert failed for %s/%s: %s", provider, idempotency_key, e)
        raise

    event_id = resp.data[0]["id"] if resp.data else None
    return {"status": "persisted", "event_id": event_id}


async def _enqueue(request: Request, task: str, event_id: str) -> None:
    """Enqueue a processing task on the app's arq pool. On failure the row stays
    'pending' and the reconciler re-enqueues it (Redis-briefly-down edge case).

    Uses a deterministic ``_job_id`` (same scheme as the reconciler) so the
    initial enqueue and a reconcile re-enqueue can never create two concurrent
    jobs for the same event."""
    from utils.reconcile import _job_id

    arq = getattr(request.app.state, "arq", None)
    if arq is None:
        logger.warning("arq pool unavailable — leaving event %s pending for reconcile", event_id)
        return
    try:
        await arq.enqueue_job(task, event_id, _job_id=_job_id(event_id))
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
    owning client, **decrypts** the stored GBP access token (both tokens are
    Fernet-encrypted at rest by ``auth.gbp_callback``), and GETs the review. On a
    401 the access token is refreshed (using the decrypted refresh token) and the
    request retried once.

    Returns the review resource dict. Returns ``{}`` only when the client/review
    cannot be resolved (unrecoverable). RAISES on transport/auth failure so the
    caller keeps the delivery retryable instead of persisting an empty review.
    """
    import httpx
    from services.crypto import decrypt
    from services.gbp import GBP_REVIEWS_BASE, refresh_access_token

    client = resolve_client_from_location(review_name)
    if not client:
        logger.warning("fetch_review_resource: no client for %s", review_name)
        return {}

    enc_access = client.get("gbp_access_token", "")
    enc_refresh = client.get("gbp_refresh_token", "")
    access_token = decrypt(enc_access) if enc_access else ""
    refresh_token = decrypt(enc_refresh) if enc_refresh else ""
    if not access_token and refresh_token:
        access_token = await refresh_access_token(refresh_token)

    url = f"{GBP_REVIEWS_BASE}/{review_name}"

    async def _get(token: str):
        async with httpx.AsyncClient() as http:
            resp = await http.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
            resp.raise_for_status()
            return resp.json()

    try:
        return await _get(access_token)
    except httpx.HTTPStatusError as e:
        # Refresh + retry once on an expired/invalid access token.
        if e.response is not None and e.response.status_code == 401 and refresh_token:
            logger.info("fetch_review_resource: 401 — refreshing token and retrying")
            access_token = await refresh_access_token(refresh_token)
            return await _get(access_token)
        logger.error("fetch_review_resource GET failed for %s: %s", review_name, e)
        raise


@router.post("/inbound-review")
async def inbound_review(request: Request):
    """GBP review notification (Pub/Sub push). Decode envelope, dedupe by
    ``messageId`` BEFORE any provider call, fetch the review resource, persist +
    enqueue. Returns 200 fast.

    Ordering matters: dedup happens first so a duplicate delivery never triggers
    a second GBP fetch. A failed/empty fetch is never persisted-and-marked-done —
    it returns a non-2xx so Pub/Sub redelivers and we retry the fetch.
    """
    envelope = await request.json()
    try:
        decoded = decode_pubsub_envelope(envelope)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid Pub/Sub envelope: {e}")

    message_id = decoded["message_id"]
    notification = decoded["notification"]

    # Dedup FIRST — before any provider work — so duplicate deliveries don't
    # re-hit the GBP API (and don't race).
    db = get_db()
    existing = (
        db.table("webhook_events")
        .select("id, status")
        .eq("provider", "gbp")
        .eq("idempotency_key", message_id)
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        return {"status": "duplicate", "event_id": existing.data["id"]}

    # The notification identifies the review resource (accounts/.../reviews/{id}).
    review_name = (
        notification.get("review")
        or notification.get("name")
        or notification.get("reviewName", "")
    )

    try:
        review = await fetch_review_resource(review_name) if review_name else {}
    except Exception as e:
        # Transport/auth failure — keep the delivery retryable (Pub/Sub redelivers)
        # rather than persisting an empty review and marking it done.
        logger.error("inbound_review: review fetch failed for %s: %s", review_name, e)
        raise HTTPException(status_code=502, detail="Failed to fetch review resource")

    if not review:
        # Could not obtain the review resource (no client / no resource name).
        # Do not persist an empty payload as done — 502 keeps it retryable.
        logger.warning("inbound_review: empty review resource for %s", review_name)
        raise HTTPException(status_code=502, detail="Empty review resource")

    payload = dict(review)
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
        # Claude not yet wired up — a genuine "skip", not a failure. Returning
        # normally lets the inbound task mark the event done.
        logger.warning("claude.py not yet implemented — skipping draft generation")
        return
    except Exception as e:
        # A real Claude API/transport failure MUST propagate so the durable
        # inbound task retries and eventually dead-letters — never marks done.
        logger.error(f"Claude draft generation failed: {e}")
        raise

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
