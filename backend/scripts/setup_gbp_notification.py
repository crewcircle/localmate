#!/usr/bin/env python3
"""Register GBP Pub/Sub notifications for a client account (thin CLI wrapper).

This script is the manual-fallback path for the automated provisioning flow.
The automated path runs via arq enqueue from ``routers/auth.py::gbp_callback``
(see ``services/gbp_provisioning.py::provision_gbp_notifications``). Both paths
share the same code, so the CLI and the automated flow are always in sync.

Usage:
    python3 backend/scripts/setup_gbp_notification.py --client-id <UUID>

The GBP account id and Pub/Sub topic are resolved automatically by
``provision_gbp_notifications`` from the locations table (C2) and config
(``gcp_project_id`` / ``gbp_pubsub_topic_name``).
"""

import argparse
import asyncio
import logging
import sys


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Register GBP Pub/Sub review notifications (thin wrapper).",
    )
    p.add_argument("--client-id", required=True, help="Client UUID in localmate DB.")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()

    from services.gbp_provisioning import provision_gbp_notifications

    try:
        result = asyncio.run(provision_gbp_notifications(args.client_id))
    except Exception as exc:
        logging.error("Provisioning failed: %s", exc)
        sys.exit(1)

    status = result.get("status")
    if status == "active":
        print("GBP notification provisioning complete.")
        print(f"  Account:  {result.get('account_id', '?')}")
        print(f"  Topic:    {result.get('topic', '?')}")
    else:
        print(f"GBP notification provisioning failed: {result.get('error', '?')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
