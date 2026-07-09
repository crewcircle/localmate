from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging

logger = logging.getLogger(__name__)
AEST = pytz.timezone("Australia/Sydney")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=AEST)

    # Yelp polling — every 24 hours (added in Phase 3)
    try:
        from jobs.review_poll import poll_yelp_reviews_all_clients
        scheduler.add_job(poll_yelp_reviews_all_clients, CronTrigger(hour="*/24"), id="yelp_poll")
    except ImportError:
        logger.warning("yelp_poll job not yet implemented — skipping")

    # SEO monitoring — Monday 6am AEST (added in Phase 4)
    try:
        from jobs.seo_report import run_seo_rankings_all_clients
        scheduler.add_job(run_seo_rankings_all_clients, CronTrigger(day_of_week="mon", hour=6), id="seo_weekly")
    except ImportError:
        logger.warning("seo_weekly job not yet implemented — skipping")

    # Competitor snapshot — Sunday 10pm AEST (added in Phase 5)
    try:
        from jobs.competitor_watch import run_competitor_snapshots_all_clients
        scheduler.add_job(run_competitor_snapshots_all_clients, CronTrigger(day_of_week="sun", hour=22), id="competitor_weekly")
    except ImportError:
        logger.warning("competitor_weekly job not yet implemented — skipping")

    # Appointment follow-up — daily 8am AEST (added in Phase 6)
    try:
        from jobs.appointment_followup import run_appointment_followup_all_clients
        scheduler.add_job(run_appointment_followup_all_clients, CronTrigger(hour=8), id="appointment_daily")
    except ImportError:
        logger.warning("appointment_daily job not yet implemented — skipping")

    # Check trial expiries — hourly (added in Phase 2)
    try:
        from middleware.trial_gate import check_trial_expiries
        scheduler.add_job(check_trial_expiries, CronTrigger(minute=0), id="trial_hourly")
    except ImportError:
        logger.warning("trial_hourly job not yet implemented — skipping")

    return scheduler
