#!/usr/bin/env python3
"""Register GBP Pub/Sub notifications for a client account.

Links a GCP Pub/Sub topic to a Google Business Profile account so review
notifications flow through to our inbound-review webhook.

Prerequisites (manual, in GCP console):
  1. Create a Pub/Sub topic.
  2. Grant mybusiness-api-pubsub@system.gserviceaccount.com the
     pubsub.topics.publish IAM role on that topic.
  3. Create a push subscription on the topic targeting:
     https://api.localmate.crewcircle.com.au/webhooks/inbound-review

API: PATCH https://mybusinessnotifications.googleapis.com/v1/accounts/{account}/notificationSetting
Context7: /websites/developers_google_my-business  (notification-setup)

Usage:
    python3 backend/scripts/setup_gbp_notification.py \
        --client-id <UUID> \
        --account-id <GBP_ACCOUNT_ID> \
        --pubsub-topic projects/<gcp-project>/topics/gbp-reviews
"""

import argparse
import asyncio
import logging
import sys
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

NOTIFICATIONS_BASE = "https://mybusinessnotifications.googleapis.com/v1"
REVIEW_NOTIFICATION_TYPES = ["NEW_REVIEW", "UPDATED_REVIEW"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Register GBP Pub/Sub review notifications.",
    )
    p.add_argument("--client-id", required=True, help="Client UUID in localmate DB.")
    p.add_argument("--account-id", required=True, help="GBP account ID (numeric).")
    p.add_argument(
        "--pubsub-topic",
        required=True,
        help="Full Pub/Sub topic resource name, e.g. projects/my-proj/topics/gbp-reviews",
    )
    return p.parse_args()


def _fetch_access_token(client_id: str) -> str:
    from db import get_db
    from services.crypto import decrypt

    db = get_db()
    row = (
        db.table("clients")
        .select("gbp_access_token")
        .eq("id", client_id)
        .single()
        .execute()
    )
    if not row.data or not row.data.get("gbp_access_token"):
        raise ValueError(f"Client {client_id} has no stored GBP access token")
    return decrypt(row.data["gbp_access_token"])


def _get_current_setting(
    account_id: str, access_token: str
) -> Optional[dict]:
    url = f"{NOTIFICATIONS_BASE}/accounts/{account_id}/notificationSetting"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        with httpx.Client() as client:
            resp = client.get(url, headers=headers, timeout=15)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.error("Failed to read current notification setting: %s", exc)
        return None


def _already_registered(setting: Optional[dict], topic: str) -> bool:
    if setting is None:
        return False
    current_topic = setting.get("pubsubTopic", "")
    current_types = set(setting.get("notificationTypes", []))
    return current_topic == topic and current_types >= set(REVIEW_NOTIFICATION_TYPES)


def _register_notification(
    account_id: str, access_token: str, pubsub_topic: str
) -> dict:
    url = (
        f"{NOTIFICATIONS_BASE}/accounts/{account_id}/notificationSetting"
        "?updateMask=pubsubTopic,notificationTypes"
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "pubsubTopic": pubsub_topic,
        "notificationTypes": REVIEW_NOTIFICATION_TYPES,
    }
    with httpx.Client() as client:
        resp = client.patch(url, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        return resp.json()


def main() -> None:
    args = parse_args()

    try:
        access_token = _fetch_access_token(args.client_id)
    except Exception as exc:
        logger.error("Could not fetch client credentials: %s", exc)
        sys.exit(1)

    current = _get_current_setting(args.account_id, access_token)
    if _already_registered(current, args.pubsub_topic):
        print(f"Already registered. Topic: {args.pubsub_topic}")
        print("No changes needed.")
        return

    try:
        result = _register_notification(
            args.account_id, access_token, args.pubsub_topic
        )
    except Exception as exc:
        logger.error("Registration failed: %s", exc)
        sys.exit(1)

    print("Notification setting registered successfully.")
    print(f"  Account:  {args.account_id}")
    print(f"  Topic:    {result.get('pubsubTopic', args.pubsub_topic)}")
    print(f"  Types:    {result.get('notificationTypes', REVIEW_NOTIFICATION_TYPES)}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    main()
