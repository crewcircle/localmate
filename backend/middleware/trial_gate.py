from datetime import datetime, timedelta
import pytz
import logging
from db import get_db
from config import settings

AEST = pytz.timezone("Australia/Sydney")
logger = logging.getLogger(__name__)

TRIAL_CAPS = {
    "review_drafts": 100,
    "seo_reports": 2,
    "competitor_briefs": 1,
    "followup_messages": 50,
}


async def check_trial_gate(client_id: str, job_type: str) -> dict:
    """Check if client can use this job type. Returns {allowed: bool, reason: str}."""
    db = get_db()
    resp = db.table("clients").select("trial_status, trial_ends_at, subscription_status, trial_usage").eq("id", client_id).single().execute()
    if not resp.data:
        return {"allowed": False, "reason": "Client not found"}

    client = resp.data
    # Active subscription bypasses trial checks
    if client["subscription_status"] == "active":
        return {"allowed": True, "reason": "active_subscription"}

    # Trial expired
    if client["trial_status"] == "expired" or client["subscription_status"] == "trial_expired":
        return {"allowed": False, "reason": "trial_expired"}

    # Trial still active — check cap
    trial_ends = datetime.fromisoformat(client["trial_ends_at"])
    if datetime.now(AEST) > trial_ends:
        return {"allowed": False, "reason": "trial_expired"}

    usage = client.get("trial_usage", {}) or {}
    used = usage.get(job_type, 0)
    cap = TRIAL_CAPS.get(job_type, 0)
    if used >= cap:
        return {"allowed": False, "reason": f"trial_cap_reached ({used}/{cap})"}

    return {"allowed": True, "reason": "trial_active"}


async def increment_trial_usage(client_id: str, job_type: str) -> None:
    """Atomically increment trial usage via Postgres function."""
    db = get_db()
    db.rpc("increment_trial_usage", {"p_client_id": client_id, "p_job_type": job_type}).execute()


async def expire_trial(client_id: str) -> None:
    """Mark trial as expired and send notification email."""
    db = get_db()
    db.table("clients").update({
        "trial_status": "expired",
        "subscription_status": "trial_expired"
    }).eq("id", client_id).execute()
    # Send trial expired email
    try:
        from services.resend_email import send_trial_expired_email
        client = db.table("clients").select("email, business_name").eq("id", client_id).single().execute()
        if client.data:
            await send_trial_expired_email(client.data["email"], client.data["business_name"])
    except Exception as e:
        logger.error(f"Failed to send trial expired email for {client_id}: {e}")


async def check_trial_expiries() -> None:
    """APScheduler job — runs hourly. Checks for trials ending and sends appropriate emails."""
    db = get_db()
    now = datetime.now(AEST)

    # Find trials expiring in <= 2 days but not yet expired — send card_required email (if not already sent)
    soon = now + timedelta(days=2)
    soon_resp = db.table("clients").select("id, email, business_name, trial_ends_at, trial_status, card_collected_at").eq("trial_status", "active").lt("trial_ends_at", soon.isoformat()).execute()
    if soon_resp.data:
        for client in soon_resp.data:
            if not client.get("card_collected_at"):
                try:
                    from services.resend_email import send_trial_ending_email
                    await send_trial_ending_email(client["email"], client["business_name"], client["id"])
                except Exception as e:
                    logger.error(f"Failed to send trial-ending email for {client['id']}: {e}")

    # Find expired trials — mark expired
    expired_resp = db.table("clients").select("id, email, business_name").eq("trial_status", "active").lt("trial_ends_at", now.isoformat()).execute()
    if expired_resp.data:
        for client in expired_resp.data:
            await expire_trial(client["id"])
