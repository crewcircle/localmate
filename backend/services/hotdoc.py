"""HotDoc booking adapter (fail-safe stub).

HotDoc has no open/public API — clinics connect HotDoc to their underlying PMS
(Genie, Core Practice, Nookal, Cliniko). This stub registers HotDoc in the adapter
registry with ``SUPPORTS_REBOOK=False`` so the daily Rebook job fails safe (logs
"no open API, connect underlying PMS" and skips) rather than 404ing. It is the seam
to fill once partner access lands.

Fallback (documented for onboarding): read the underlying PMS the clinic already
runs behind HotDoc (configure that PMS as the booking_system instead), or apply for
HotDoc partner access and replace this stub with a real adapter.
"""
import logging

logger = logging.getLogger(__name__)

# --- Adapter capability metadata (read by jobs/appointment_followup.py) ---
ADAPTER_NAME = "hotdoc"
ID_COLUMN = "hotdoc_id"             # patients table column (rarely populated)
CREDENTIAL_KEYS: list[str] = []
SUPPORTS_REBOOK = False
AUTH_MODEL = "partner_gated"

_FALLBACK_MSG = (
    "HotDoc has no open API — connect the underlying PMS (Cliniko/Nookal) instead. "
    "Skipping appointment follow-up for this client."
)


async def get_appointments(client: dict, date_from: str, date_to: str, status: str = "completed") -> list[dict]:
    """HotDoc has no usable public API. Logs the fallback and returns ``[]``."""
    logger.warning(_FALLBACK_MSG)
    return []


async def get_future_appointments(client: dict, patient_id: str, after: str) -> list[dict]:
    """HotDoc has no usable public API. Logs the fallback and returns ``[]``."""
    logger.warning(_FALLBACK_MSG)
    return []
