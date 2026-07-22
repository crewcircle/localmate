"""Billing router — usage visibility + Stripe Billing Portal (Phase 1).

All ``/billing/*`` client-scoped routes live here under a single ``/billing``
prefix (D7-A). ``/auth/billing/setup-*`` stays in ``routers/auth.py`` so the
dashboard's existing SetupIntent calls keep working.

Tenant scoping (C8/D20): ``client_id`` is derived from the authenticated
identity via :func:`middleware.auth.require_client_id` — never from the request
body/query — so a user can only ever see / act on their own tenant.
"""
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException

from config import settings
from db import get_db
from middleware.auth import require_client_id
from middleware.trial_gate import TRIAL_CAPS

router = APIRouter()
logger = logging.getLogger(__name__)
stripe.api_key = settings.stripe_secret_key


@router.get("/usage")
async def billing_usage(client_id: str = Depends(require_client_id)):
    """Per-job-type trial usage (used / cap / remaining) + trial/subscription state.

    Caps are sourced from :data:`middleware.trial_gate.TRIAL_CAPS` (single source
    of truth). An active subscription reports unlimited caps (``cap``/``remaining``
    as ``null``) to mirror the :func:`check_trial_gate` bypass. Only the keys in
    ``TRIAL_CAPS`` are reported; a job type absent from ``trial_usage`` is treated
    as 0 used.
    """
    db = get_db()
    resp = (
        db.table("clients")
        .select("trial_status, trial_ends_at, subscription_status, trial_usage")
        .eq("id", client_id)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Client not found")

    client = resp.data
    usage_map = client.get("trial_usage") or {}
    active = client.get("subscription_status") == "active"

    usage = {}
    for job_type, cap in TRIAL_CAPS.items():
        used = usage_map.get(job_type, 0)
        if active:
            # Paid = unlimited (D6-A): mirror the trial-gate bypass.
            usage[job_type] = {"used": used, "cap": None, "remaining": None}
        else:
            usage[job_type] = {"used": used, "cap": cap, "remaining": max(cap - used, 0)}

    return {
        "trial_status": client.get("trial_status"),
        "trial_ends_at": client.get("trial_ends_at"),
        "subscription_status": client.get("subscription_status"),
        "usage": usage,
    }


@router.post("/portal")
async def billing_portal(client_id: str = Depends(require_client_id)):
    """Create a Stripe Billing Portal session for self-serve plan/card/cancel.

    Returns ``{"url": ...}``. The dashboard redirects to ``url``. Portal-driven
    subscription changes flow back through the existing Stripe webhook handlers
    (``customer.subscription.updated`` / ``deleted``) — no new reconciliation path.
    """
    db = get_db()
    resp = (
        db.table("clients")
        .select("stripe_customer_id")
        .eq("id", client_id)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Client not found")

    customer_id = resp.data.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=422, detail="No Stripe customer id for this client")

    return_url = settings.dashboard_url or "https://localmate.crewcircle.co/dashboard/settings"
    params = {"customer": customer_id, "return_url": return_url}
    # `configuration` (NOT `configuration_id`) is the verified Stripe API param.
    # Pass it only when a portal config id is configured; omit to use the
    # Stripe dashboard default portal config.
    if settings.stripe_portal_config_id:
        params["configuration"] = settings.stripe_portal_config_id

    try:
        session = stripe.billing_portal.Session.create(**params)
    except Exception as e:
        logger.error("Stripe billing portal session failed for %s: %s", client_id, e)
        raise HTTPException(status_code=502, detail="Billing portal unavailable")

    return {"url": session.url}
