from datetime import datetime, timedelta
import pytz
import stripe
import logging
from fastapi import APIRouter, HTTPException, Query
from db import get_db
from config import settings
from services.crypto import encrypt
from services.gbp import exchange_code_for_tokens

router = APIRouter()
AEST = pytz.timezone("Australia/Sydney")
logger = logging.getLogger(__name__)
stripe.api_key = settings.stripe_secret_key


@router.post("/signup")
async def signup(payload: dict):
    """Create new client with 14-day trial. No card required."""
    required = ["business_name", "business_type", "email", "suburb", "state", "selected_jobs"]
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=422, detail=f"Missing field: {field}")

    now = datetime.now(AEST)
    trial_ends = now + timedelta(days=14)

    try:
        customer = stripe.Customer.create(
            email=payload["email"],
            name=payload["business_name"],
            metadata={"signup_source": "trial", "project": settings.project_id},
            address={"city": payload["suburb"], "state": payload["state"], "country": "AU"}
        )
    except Exception as e:
        logger.error(f"Stripe customer creation failed: {e}")
        raise HTTPException(status_code=502, detail="Payment provider error")

    db = get_db()
    existing = db.table("clients").select("id").eq("email", payload["email"]).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Email already registered")

    client = db.table("clients").insert({
        "business_name": payload["business_name"],
        "business_type": payload["business_type"],
        "email": payload["email"],
        "suburb": payload["suburb"],
        "state": payload["state"],
        "active_jobs": payload["selected_jobs"],
        "trial_started_at": now.isoformat(),
        "trial_ends_at": trial_ends.isoformat(),
        "trial_status": "active",
        "stripe_customer_id": customer["id"],
        "subscription_status": "trialing",
        "trial_usage": {"review_drafts": 0, "seo_reports": 0, "competitor_briefs": 0, "followup_messages": 0}
    }).execute()

    client_id = client.data[0]["id"]

    try:
        from services.resend_email import send_welcome_email
        await send_welcome_email(payload["email"], payload["business_name"], client_id)
    except Exception as e:
        logger.error(f"Welcome email failed: {e}")

    return {"client_id": client_id, "trial_ends_at": trial_ends.isoformat()}


@router.get("/gbp-oauth-url")
async def get_gbp_oauth_url(client_id: str = Query(...)):
    """Get Google Business Profile OAuth URL for a client."""
    try:
        from services.gbp import get_gbp_auth_url
        url = get_gbp_auth_url(client_id)
        return {"oauth_url": url}
    except ImportError:
        raise HTTPException(status_code=501, detail="GBP service not yet configured")
    except Exception as e:
        logger.error(f"GBP OAuth URL failed for {client_id}: {e}")
        raise HTTPException(status_code=500, detail="OAuth URL generation failed")


@router.get("/gbp-callback")
async def gbp_callback(code: str = Query(...), state: str = Query(...)):
    """Google OAuth callback — exchange code, encrypt tokens, store on client."""
    client_id = state
    try:
        token_response = await exchange_code_for_tokens(code)
        if "access_token" not in token_response:
            raise ValueError("GBP token exchange missing access_token")

        encrypted_access = encrypt(token_response["access_token"])
        encrypted_refresh = encrypt(token_response.get("refresh_token", ""))
        location_id = token_response.get("resourceName", "").split("/")[-1] or None

        db = get_db()
        db.table("clients").update({
            "gbp_access_token": encrypted_access,
            "gbp_refresh_token": encrypted_refresh,
            "gbp_location_id": location_id,
        }).eq("id", client_id).execute()

        return {"status": "connected", "client_id": client_id}
    except ValueError as e:
        logger.error(f"GBP OAuth validation failed for {client_id}: {e}")
        raise HTTPException(status_code=400, detail=f"GBP OAuth failed: {e}")
    except Exception as e:
        logger.error(f"GBP OAuth callback failed for {client_id}: {e}")
        raise HTTPException(status_code=400, detail=f"GBP OAuth failed: {e}")


@router.post("/billing/setup-complete")
async def billing_setup_complete(payload: dict):
    """Complete billing setup — create Stripe subscription with trial end timestamp."""
    client_id = payload.get("client_id")
    payment_method_id = payload.get("payment_method_id")
    if not client_id or not payment_method_id:
        raise HTTPException(status_code=422, detail="Missing client_id or payment_method_id")

    db = get_db()
    resp = db.table("clients").select("stripe_customer_id, trial_ends_at").eq("id", client_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Client not found")

    customer_id = resp.data["stripe_customer_id"]
    trial_ends_at = resp.data["trial_ends_at"]

    try:
        stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
        stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": payment_method_id})

        subscription_params = {
            "customer": customer_id,
            "items": [{"price": settings.stripe_price_id}],
            "trial_end": int(datetime.fromisoformat(trial_ends_at).timestamp()),
            "payment_settings": {"payment_method_types": ["card", "au_becs_debit"]},
        }
        if settings.stripe_gst_rate_id:
            subscription_params["default_tax_rates"] = [settings.stripe_gst_rate_id]

        subscription = stripe.Subscription.create(**subscription_params)
    except Exception as e:
        logger.error(f"Stripe subscription creation failed for {client_id}: {e}")
        raise HTTPException(status_code=502, detail="Payment setup failed")

    now = datetime.now(AEST)
    db.table("clients").update({
        "trial_status": "converted",
        "subscription_status": "trialing",
        "stripe_subscription_id": subscription["id"],
        "card_collected_at": now.isoformat()
    }).eq("id", client_id).execute()

    return {"subscription_id": subscription["id"], "status": "active"}


@router.post("/billing/setup-intent")
async def billing_setup_intent(payload: dict):
    """Create a Stripe SetupIntent for dashboard 'Add card' flow."""
    client_id = payload.get("client_id")
    if not client_id:
        raise HTTPException(status_code=422, detail="Missing client_id")

    try:
        db = get_db()
        resp = db.table("clients").select("stripe_customer_id").eq("id", client_id).single().execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Client not found")

        customer_id = resp.data["stripe_customer_id"]
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card", "au_becs_debit"],
            usage="off_session",
        )
        return {"client_secret": setup_intent.client_secret}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stripe SetupIntent failed for {client_id}: {e}")
        raise HTTPException(status_code=502, detail="Payment setup failed")
