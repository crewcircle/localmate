"""PracticePal booking adapter (fail-safe stub).

PracticePal has no released public API (its privacy policy states the API is "not
yet released"; the product is UK-focused). This stub registers PracticePal in the
adapter registry with ``SUPPORTS_REBOOK=False`` so the daily Rebook job fails safe
(logs "API not yet released" and skips) rather than 404ing. It is the seam to fill
if/when an API ships.

Fallback (documented for onboarding): manual/CSV import of lapsed patients; revisit
when PracticePal releases an API.
"""
import logging

logger = logging.getLogger(__name__)

# --- Adapter capability metadata (read by jobs/appointment_followup.py) ---
ADAPTER_NAME = "practicepal"
ID_COLUMN = "practicepal_id"        # patients table column (rarely populated)
CREDENTIAL_KEYS: list[str] = []
SUPPORTS_REBOOK = False
AUTH_MODEL = "none"

_FALLBACK_MSG = (
    "PracticePal API is not yet released — skipping appointment follow-up for this "
    "client. Revisit when an API becomes available."
)


async def get_appointments(client: dict, date_from: str, date_to: str, status: str = "completed") -> list[dict]:
    """PracticePal has no released public API. Logs the fallback and returns ``[]``."""
    logger.warning(_FALLBACK_MSG)
    return []


async def get_future_appointments(client: dict, patient_id: str, after: str) -> list[dict]:
    """PracticePal has no released public API. Logs the fallback and returns ``[]``."""
    logger.warning(_FALLBACK_MSG)
    return []
