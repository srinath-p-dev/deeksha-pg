"""Background worker: run with `python -m app.worker.main`.

Runs separately from the API so jobs never run twice (even with several API
processes) and API restarts don't interrupt sending.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.worker import dispatcher, jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("worker")


def main() -> None:
    tz = settings.tz
    dispatcher.recover_stuck()
    jobs.catch_up()

    scheduler = BlockingScheduler(timezone=tz)
    common = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 60 * 60}

    scheduler.add_job(jobs.generate_rent, CronTrigger(hour=0, minute=5, timezone=tz), **common)
    r = settings.reminder_at
    scheduler.add_job(
        jobs.rent_reminders,
        CronTrigger(day=settings.reminder_days, hour=r.hour, minute=r.minute, timezone=tz),
        **common,
    )
    o = settings.owner_report_at
    scheduler.add_job(
        jobs.owner_report,
        CronTrigger(day=settings.owner_report_day, hour=o.hour, minute=o.minute, timezone=tz),
        **common,
    )
    scheduler.add_job(dispatcher.dispatch_pending, IntervalTrigger(seconds=20), **common)
    scheduler.add_job(jobs.whatsapp_health, IntervalTrigger(minutes=1), **common)

    log.info(
        "Worker started. Reminders: days %s at %s IST; owner report: day %s at %s IST",
        settings.reminder_days, settings.reminder_time,
        settings.owner_report_day, settings.owner_report_time,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
