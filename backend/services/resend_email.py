import logging
from config import settings

logger = logging.getLogger(__name__)


def _get_resend():
    import resend
    resend.api_key = settings.resend_api_key
    return resend


def _send(to: str, subject: str, html: str) -> dict:
    """Send an email via Resend, raising on any transport/provider failure.

    Returns the Resend response. Callers that want fire-and-forget behaviour
    wrap this in try/except; the durable task path (:func:`send_email_strict`)
    lets the exception propagate so arq can retry / dead-letter.
    """
    r = _get_resend()
    return r.Emails.send(
        from_email=f"hello@{settings.base_domain}",
        to_email=to,
        subject=subject,
        html=html,
    )


# kind -> builder(business_name) -> (subject, html). Kept as the single source of
# truth for both the swallowing senders below and the strict durable dispatcher.
def _content(kind: str, business_name: str) -> tuple[str, str]:
    templates = {
        "welcome": (
            f"Welcome to Local Biz Automation, {business_name}!",
            f"<p>Hi {business_name} team,</p><p>Your 14-day trial is now active. You have full access to all features.</p><p>Get started: <a href='https://{settings.base_domain}/dashboard'>Open your dashboard</a></p>",
        ),
        "trial_day1": (
            f"Quick setup checklist for {business_name}",
            "<p>Here are 3 things to do today to get the most out of your trial:</p><ol><li>Connect your Google Business Profile</li><li>Add your top 5 SEO keywords</li><li>Review your first AI-drafted response</li></ol>",
        ),
        "trial_day7": (
            f"You're halfway through your trial, {business_name}",
            "<p>Here's what we've done for you so far...</p>",
        ),
        "trial_day12": (
            f"Action needed: Add your card before trial ends, {business_name}",
            "<p>Your trial ends in 2 days. Add your card now to keep your data and continue without interruption.</p>",
        ),
        "trial_day13": (
            f"Final reminder: trial ends tomorrow, {business_name}",
            "<p>This is your final reminder. Add your card now to avoid losing access.</p>",
        ),
        "trial_expired": (
            f"Your trial has ended, {business_name}",
            "<p>Your trial has ended. Upgrade to restore access to your dashboard and saved data.</p>",
        ),
        "trial_ending": (
            f"Your trial ends soon, {business_name} — add your card",
            "<p>Your trial ends in 2 days. Add your card to continue without interruption.</p>",
        ),
    }
    if kind not in templates:
        raise ValueError(f"unknown email kind: {kind}")
    return templates[kind]


async def send_email_strict(kind: str, to: str, business_name: str, *args) -> dict:
    """Send email and RAISE on failure — used by the durable arq task.

    Unlike the ``send_*_email`` helpers below, this does not swallow errors, so
    the durable wrapper can retry and eventually dead-letter. ``args`` (e.g. the
    client_id) are accepted for signature compatibility with the callers.
    """
    subject, html = _content(kind, business_name)
    return _send(to, subject, html)


async def send_welcome_email(to: str, business_name: str, client_id: str) -> None:
    """Day 0 — welcome email sent immediately on signup."""
    try:
        subject, html = _content("welcome", business_name)
        _send(to, subject, html)
    except Exception as e:
        logger.error(f"send_welcome_email failed: {e}")


async def send_trial_day1_email(to: str, business_name: str, client_id: str) -> None:
    """Day 1 — setup checklist."""
    try:
        subject, html = _content("trial_day1", business_name)
        _send(to, subject, html)
    except Exception as e:
        logger.error(f"send_trial_day1_email failed: {e}")


async def send_trial_day7_email(to: str, business_name: str, client_id: str) -> None:
    """Day 7 — value recap."""
    try:
        subject, html = _content("trial_day7", business_name)
        _send(to, subject, html)
    except Exception as e:
        logger.error(f"send_trial_day7_email failed: {e}")


async def send_trial_day12_email(to: str, business_name: str, client_id: str) -> None:
    """Day 12 — add card prompt."""
    try:
        subject, html = _content("trial_day12", business_name)
        _send(to, subject, html)
    except Exception as e:
        logger.error(f"send_trial_day12_email failed: {e}")


async def send_trial_day13_email(to: str, business_name: str, client_id: str) -> None:
    """Day 13 — final warning."""
    try:
        subject, html = _content("trial_day13", business_name)
        _send(to, subject, html)
    except Exception as e:
        logger.error(f"send_trial_day13_email failed: {e}")


async def send_trial_expired_email(to: str, business_name: str) -> None:
    """Trial ended — upgrade prompt."""
    try:
        subject, html = _content("trial_expired", business_name)
        _send(to, subject, html)
    except Exception as e:
        logger.error(f"send_trial_expired_email failed: {e}")


async def send_trial_ending_email(to: str, business_name: str, client_id: str) -> None:
    """Trial ending soon — card required email."""
    try:
        subject, html = _content("trial_ending", business_name)
        _send(to, subject, html)
    except Exception as e:
        logger.error(f"send_trial_ending_email failed: {e}")
