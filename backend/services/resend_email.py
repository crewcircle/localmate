import logging
from config import settings

logger = logging.getLogger(__name__)


def _get_resend():
    import resend
    resend.api_key = settings.resend_api_key
    return resend


async def send_welcome_email(to: str, business_name: str, client_id: str) -> None:
    """Day 0 — welcome email sent immediately on signup."""
    try:
        r = _get_resend()
        r.Emails.send(
            from_email=f"hello@{settings.base_domain}",
            to_email=to,
            subject=f"Welcome to Local Biz Automation, {business_name}!",
            html=f"<p>Hi {business_name} team,</p><p>Your 14-day trial is now active. You have full access to all features.</p><p>Get started: <a href='https://{settings.base_domain}/dashboard'>Open your dashboard</a></p>"
        )
    except Exception as e:
        logger.error(f"send_welcome_email failed: {e}")


async def send_trial_day1_email(to: str, business_name: str, client_id: str) -> None:
    """Day 1 — setup checklist."""
    try:
        r = _get_resend()
        r.Emails.send(
            from_email=f"hello@{settings.base_domain}",
            to_email=to,
            subject=f"Quick setup checklist for {business_name}",
            html=f"<p>Here are 3 things to do today to get the most out of your trial:</p><ol><li>Connect your Google Business Profile</li><li>Add your top 5 SEO keywords</li><li>Review your first AI-drafted response</li></ol>"
        )
    except Exception as e:
        logger.error(f"send_trial_day1_email failed: {e}")


async def send_trial_day7_email(to: str, business_name: str, client_id: str) -> None:
    """Day 7 — value recap."""
    try:
        r = _get_resend()
        r.Emails.send(
            from_email=f"hello@{settings.base_domain}",
            to_email=to,
            subject=f"You're halfway through your trial, {business_name}",
            html=f"<p>Here's what we've done for you so far...</p>"
        )
    except Exception as e:
        logger.error(f"send_trial_day7_email failed: {e}")


async def send_trial_day12_email(to: str, business_name: str, client_id: str) -> None:
    """Day 12 — add card prompt."""
    try:
        r = _get_resend()
        r.Emails.send(
            from_email=f"hello@{settings.base_domain}",
            to_email=to,
            subject=f"Action needed: Add your card before trial ends, {business_name}",
            html=f"<p>Your trial ends in 2 days. Add your card now to keep your data and continue without interruption.</p>"
        )
    except Exception as e:
        logger.error(f"send_trial_day12_email failed: {e}")


async def send_trial_day13_email(to: str, business_name: str, client_id: str) -> None:
    """Day 13 — final warning."""
    try:
        r = _get_resend()
        r.Emails.send(
            from_email=f"hello@{settings.base_domain}",
            to_email=to,
            subject=f"Final reminder: trial ends tomorrow, {business_name}",
            html=f"<p>This is your final reminder. Add your card now to avoid losing access.</p>"
        )
    except Exception as e:
        logger.error(f"send_trial_day13_email failed: {e}")


async def send_trial_expired_email(to: str, business_name: str) -> None:
    """Trial ended — upgrade prompt."""
    try:
        r = _get_resend()
        r.Emails.send(
            from_email=f"hello@{settings.base_domain}",
            to_email=to,
            subject=f"Your trial has ended, {business_name}",
            html=f"<p>Your trial has ended. Upgrade to restore access to your dashboard and saved data.</p>"
        )
    except Exception as e:
        logger.error(f"send_trial_expired_email failed: {e}")


async def send_trial_ending_email(to: str, business_name: str, client_id: str) -> None:
    """Trial ending soon — card required email."""
    try:
        r = _get_resend()
        r.Emails.send(
            from_email=f"hello@{settings.base_domain}",
            to_email=to,
            subject=f"Your trial ends soon, {business_name} — add your card",
            html=f"<p>Your trial ends in 2 days. Add your card to continue without interruption.</p>"
        )
    except Exception as e:
        logger.error(f"send_trial_ending_email failed: {e}")
