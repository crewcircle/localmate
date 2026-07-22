"""Jane.app booking adapter (fail-safe stub).

Jane.app has no public API — integration is via a vetted partner program only,
with no self-serve keys. This stub registers Jane in the adapter registry with
``SUPPORTS_REBOOK=False`` so the daily Rebook job fails safe (logs "partner-gated"
and skips) rather than 404ing. It is the seam to fill once partner access lands.

Fallback (documented for onboarding): manual/waitlist CSV import of lapsed
patients, or apply for the Jane partner program and replace this stub with a real
adapter.
"""
import logging

logger = logging.getLogger(__name__)

# --- Adapter capability metadata (read by jobs/appointment_followup.py) ---
ADAPTER_NAME = "jane"
ID_COLUMN = "jane_id"               # patients table column (rarely populated)
CREDENTIAL_KEYS: list[str] = []
SUPPORTS_REBOOK = False
AUTH_MODEL = "partner_gated"

_FALLBACK_MSG = (
    "Jane.app API is partner-gated (no self-serve keys) — skipping appointment "
    "follow-up for this client. Apply for the Jane partner program to enable."
)


async def get_appointments(client: dict, date_from: str, date_to: str, status: str = "completed") -> list[dict]:
    """Jane.app has no usable public API. Logs the fallback and returns ``[]``."""
    logger.warning(_FALLBACK_MSG)
    return []


async def get_future_appointments(client: dict, patient_id: str, after: str) -> list[dict]:
    """Jane.app has no usable public API. Logs the fallback and returns ``[]``."""
    logger.warning(_FALLBACK_MSG)
    return []
