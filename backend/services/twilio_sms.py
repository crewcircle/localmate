import logging
from twilio.rest import Client
from config import settings

logger = logging.getLogger(__name__)


def _get_client():
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


async def send_sms(to: str, body: str, state: str = "NSW") -> dict:
    """Send SMS via Twilio. Checks AU public holiday first — skips if holiday.

    Returns ``{sent: True, sid: ...}`` on success or
    ``{sent: False, reason: ...}`` on failure / holiday block.
    """
    # Lazy import avoids circular dependency — appointment_followup imports us.
    from jobs.appointment_followup import is_au_public_holiday
    from datetime import date

    if is_au_public_holiday(date.today(), state):
        logger.info("Skipping SMS — AU public holiday in %s", state)
        return {"sent": False, "reason": "AU public holiday — skipped"}

    try:
        client = _get_client()
        message = client.messages.create(
            body=body,
            from_=settings.twilio_au_number,
            to=to,
        )
        logger.info("SMS sent to %s — SID: %s", to, message.sid)
        return {"sent": True, "sid": message.sid}
    except Exception as e:
        logger.error("Twilio SMS send failed: %s", e)
        return {"sent": False, "reason": str(e)}
