"""GBP notification provisioning service (Phase 4 — D15-B full automation).

Automates Pub/Sub topic creation, IAM publisher binding, push subscription
creation/verification, and notification setting registration so review
webhooks flow automatically after a client completes GBP OAuth — no manual GCP
console steps for the common case.

Uses ``httpx`` for all GCP REST calls and ``PyJWT`` for service-account token
minting (both already in ``pyproject.toml`` — no new deps).

All provisioning runs **via arq enqueue** (C4), not fire-and-forget —
``provision_gbp_notifications`` is enqueued from ``routers/auth.py::gbp_callback``
via the ``provision_gbp_notifications_task`` durable wrapper in ``task_queue``.
"""
import json
import logging
import time
from datetime import datetime, timezone

import httpx
import jwt

from config import settings

logger = logging.getLogger(__name__)

PUBSUB_BASE = "https://pubsub.googleapis.com/v1"
NOTIFICATIONS_BASE = "https://mybusinessnotifications.googleapis.com/v1"
GBP_PUBLISHER_SA = "mybusiness-api-pubsub@system.gserviceaccount.com"
REVIEW_NOTIFICATION_TYPES = ["NEW_REVIEW", "UPDATED_REVIEW"]

GCP_SCOPES = [
    "https://www.googleapis.com/auth/pubsub",
    "https://www.googleapis.com/auth/cloud-platform",
]

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"


# ---------------------------------------------------------------------------
# GCP access token (service-account JWT → token exchange)
# ---------------------------------------------------------------------------

async def _gcp_access_token() -> str:
    """Mint a GCP access token from the ``GCP_SA_JSON`` service-account key.

    Uses PyJWT to sign a JWT assertion, then exchanges it for an access token
    via ``oauth2.googleapis.com/token``. No new dependencies (PyJWT already
    present in ``pyproject.toml``).
    """
    sa_json = json.loads(settings.gcp_sa_json)
    now = int(time.time())

    assertion = jwt.encode(
        {
            "iss": sa_json["client_email"],
            "scope": " ".join(GCP_SCOPES),
            "aud": OAUTH_TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        },
        sa_json["private_key"],
        algorithm="RS256",
        headers={"kid": sa_json.get("private_key_id")},
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            OAUTH_TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Pub/Sub topic + IAM + push subscription
# ---------------------------------------------------------------------------

async def ensure_topic(project: str, topic_name: str) -> str:
    """Idempotent Pub/Sub topic creation. HTTP 409 (already exists) = success.

    Returns the full topic resource name ``projects/{project}/topics/{name}``.
    """
    token = await _gcp_access_token()
    url = f"{PUBSUB_BASE}/projects/{project}/topics/{topic_name}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        resp = await client.put(url, headers=headers, timeout=15)
        if resp.status_code == 409:
            logger.info("Pub/Sub topic already exists: %s", url)
        elif resp.status_code not in (200, 201):
            resp.raise_for_status()

    return f"projects/{project}/topics/{topic_name}"


async def ensure_publisher_binding(project: str, topic_name: str) -> None:
    """Add the GBP system SA → ``roles/pubsub.publisher`` binding if absent.

    Reads the current IAM policy (``:getIamPolicy``), checks for the binding,
    and writes it back via ``:setIamPolicy`` only when it is missing.
    """
    token = await _gcp_access_token()
    topic_path = f"projects/{project}/topics/{topic_name}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PUBSUB_BASE}/{topic_path}:getIamPolicy",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        policy = resp.json()

    bindings = policy.get("bindings", [])
    has_publisher = any(
        GBP_PUBLISHER_SA in b.get("members", [])
        and b.get("role") == "roles/pubsub.publisher"
        for b in bindings
    )

    if has_publisher:
        logger.info("Publisher binding already present for %s", topic_path)
        return

    new_bindings = bindings + [
        {"role": "roles/pubsub.publisher", "members": [GBP_PUBLISHER_SA]}
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{PUBSUB_BASE}/{topic_path}:setIamPolicy",
            headers={**headers, "Content-Type": "application/json"},
            json={"policy": {"bindings": new_bindings}},
            timeout=15,
        )
        resp.raise_for_status()

    logger.info("Publisher binding added for %s", topic_path)


async def ensure_push_subscription(
    project: str, topic_name: str, push_endpoint: str
) -> str:
    """Create/verify the Pub/Sub push subscription targeting ``/webhooks/inbound-review``.

    Idempotent: GET first to check if the subscription exists, then PUT to
    create or update if absent/mismatched. This is D15-B / C9.

    Returns the full subscription resource name.
    """
    token = await _gcp_access_token()
    topic_path = f"projects/{project}/topics/{topic_name}"
    sub_name = f"{topic_name}-push"
    sub_path = f"projects/{project}/subscriptions/{sub_name}"
    url = f"{PUBSUB_BASE}/{sub_path}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        # Check if subscription already exists.
        resp = await client.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            existing = resp.json()
            if existing.get("topic") == topic_path:
                logger.info("Push subscription already exists and matches: %s", sub_path)
                return sub_path
            logger.warning("Push subscription topic mismatch — updating %s", sub_path)

        # Create or update.
        resp = await client.put(
            url,
            headers={**headers, "Content-Type": "application/json"},
            json={
                "topic": topic_path,
                "push_config": {"push_endpoint": push_endpoint},
            },
            timeout=15,
        )
        resp.raise_for_status()

    logger.info("Push subscription ready: %s → %s", sub_path, push_endpoint)
    return sub_path


# ---------------------------------------------------------------------------
# GBP notification setting registration
# ---------------------------------------------------------------------------

async def register_notification(
    account_id: str, client_access_token: str, topic: str
) -> dict:
    """Register the GBP account's notification setting (idempotent).

    Checks the current setting via GET first; if the topic + notification types
    already match, returns early. Otherwise PATCHes the setting.
    """
    url = f"{NOTIFICATIONS_BASE}/accounts/{account_id}/notificationSetting"
    headers = {"Authorization": f"Bearer {client_access_token}"}

    async with httpx.AsyncClient() as client:
        # Idempotency check.
        resp = await client.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            setting = resp.json()
            current_topic = setting.get("pubsubTopic", "")
            current_types = set(setting.get("notificationTypes", []))
            if current_topic == topic and set(REVIEW_NOTIFICATION_TYPES).issubset(
                current_types
            ):
                logger.info(
                    "Notification setting already registered for account %s", account_id
                )
                return setting

        # Register / update.
        patch_url = f"{url}?updateMask=pubsubTopic,notificationTypes"
        resp = await client.patch(
            patch_url,
            headers={**headers, "Content-Type": "application/json"},
            json={
                "pubsubTopic": topic,
                "notificationTypes": REVIEW_NOTIFICATION_TYPES,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _update_provisioning_state(db, client_id: str, status: str, **extra) -> None:
    """Persist provisioning outcome on the client row."""
    update: dict = {"provisioning_status": status}
    update.update(extra)
    db.table("clients").update(update).eq("id", client_id).execute()


async def provision_gbp_notifications(client_id: str) -> dict:
    """Orchestrate full GBP notification provisioning for a client.

    1. Resolve ``account_id`` from locations (C2 — single source of truth for
       GBP identity).
    2. Decrypt the client's GBP access token.
    3. Ensure topic + IAM + push subscription (shared single topic, D15-B).
       Skipped when ``GCP_SA_JSON`` is empty (D15-A fallback: ops step).
    4. Register the account notification setting.
    5. Persist status on the client provisioning-state columns.

    Returns ``{status: 'active'|'failed', ...}``. On failure, persists
    ``provisioning_status='failed'`` + error and returns the status dict (does
    not raise — the caller / arq wrapper decides whether to retry).
    """
    from db import get_db
    from services.crypto import decrypt

    db = get_db()

    # Load client.
    client_resp = (
        db.table("clients")
        .select("id, gbp_access_token")
        .eq("id", client_id)
        .maybe_single()
        .execute()
    )
    if not client_resp or not client_resp.data:
        _update_provisioning_state(db, client_id, "failed", provisioning_error="client not found")
        return {"status": "failed", "error": "client not found"}

    client = client_resp.data

    # Resolve account_id from locations (C2).
    loc_resp = (
        db.table("locations")
        .select("gbp_account_id, gbp_location_id")
        .eq("client_id", client_id)
        .execute()
    )
    account_id = None
    for loc in (loc_resp.data if loc_resp and loc_resp.data else []):
        if loc.get("gbp_account_id"):
            account_id = loc["gbp_account_id"]
            break

    if not account_id:
        _update_provisioning_state(
            db, client_id, "failed",
            provisioning_error="no GBP account_id found on locations",
        )
        return {"status": "failed", "error": "no GBP account_id found on locations"}

    # Decrypt access token.
    enc_token = client.get("gbp_access_token", "")
    if not enc_token:
        _update_provisioning_state(
            db, client_id, "failed", provisioning_error="no GBP access token stored"
        )
        return {"status": "failed", "error": "no GBP access token stored"}

    try:
        access_token = decrypt(enc_token)
    except Exception as e:
        _update_provisioning_state(
            db, client_id, "failed", provisioning_error=f"token decrypt failed: {e}"
        )
        return {"status": "failed", "error": f"token decrypt failed: {e}"}

    topic = f"projects/{settings.gcp_project_id}/topics/{settings.gbp_pubsub_topic_name}"
    push_endpoint = f"https://{settings.base_domain}/webhooks/inbound-review"

    try:
        # Ensure topic + IAM + push subscription (shared single topic).
        if settings.gcp_sa_json:
            await ensure_topic(settings.gcp_project_id, settings.gbp_pubsub_topic_name)
            await ensure_publisher_binding(
                settings.gcp_project_id, settings.gbp_pubsub_topic_name
            )
            await ensure_push_subscription(
                settings.gcp_project_id, settings.gbp_pubsub_topic_name, push_endpoint
            )
        else:
            # D15-A fallback: topic/IAM/subscription are one-time manual ops steps.
            logger.warning(
                "GCP_SA_JSON not configured — skipping topic/IAM/subscription setup "
                "(D15-A manual ops path)"
            )

        # Register notification setting (uses client OAuth token, not GCP SA).
        await register_notification(account_id, access_token, topic)

        # Persist success.
        now = datetime.now(timezone.utc).isoformat()
        _update_provisioning_state(
            db, client_id, "active",
            provisioning_error=None,
            pubsub_topic=topic,
            notification_registered_at=now,
        )

        logger.info(
            "GBP provisioning complete for client %s (account %s)", client_id, account_id
        )
        return {"status": "active", "account_id": account_id, "topic": topic}

    except Exception as e:
        logger.error("GBP provisioning failed for client %s: %s", client_id, e)
        _update_provisioning_state(
            db, client_id, "failed", provisioning_error=str(e)[:500]
        )
        return {"status": "failed", "error": str(e)}
