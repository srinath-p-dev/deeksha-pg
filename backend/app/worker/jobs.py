"""Scheduled jobs. Every job is idempotent: running it twice has no extra effect."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.timeutil import month_start, now_ist, today_ist
from app.messaging import whatsapp_client
from app.messaging.email import send_email
from app.models import User
from app.services.app_settings import get_app_setting, pg_name, set_app_setting
from app.services.reminders import queue_owner_report, queue_rent_reminders
from app.services.rent import generate_month

log = logging.getLogger(__name__)

ALERT_AFTER = timedelta(minutes=5)  # how long WhatsApp must be down before emailing


def generate_rent() -> None:
    with SessionLocal() as db:
        created = generate_month(db, month_start(today_ist()))
        db.commit()
    if created:
        log.info("Created %s rent record(s)", created)


def rent_reminders() -> None:
    today = today_ist()
    if today.day not in settings.reminder_day_range:
        return
    with SessionLocal() as db:
        queued = queue_rent_reminders(db, today)
        db.commit()
    log.info("Queued %s rent reminder(s)", queued)


def owner_report() -> None:
    if today_ist().day != settings.owner_report_day:
        return
    with SessionLocal() as db:
        queued = queue_owner_report(db, today_ist())
        db.commit()
    log.info("Owner report queued: %s", queued)


def _alert_emails(db) -> list[str]:
    users = db.scalars(
        select(User).where(User.receives_alerts.is_(True), User.is_active.is_(True))
    ).all()
    return [u.email for u in users if u.email]


def whatsapp_health() -> None:
    """Email the owner if WhatsApp has been disconnected for 5+ minutes (once per outage)."""
    status = whatsapp_client.get_status()
    connected = bool(status and status.get("connected"))
    now = now_ist()
    with SessionLocal() as db:
        state = get_app_setting(db, "wa_health") or {}
        if connected:
            if state.get("alerted"):
                send_email(
                    _alert_emails(db),
                    f"[{pg_name(db)}] WhatsApp reconnected",
                    "WhatsApp is connected again. Pending messages will now be sent.",
                )
            set_app_setting(db, "wa_health", {"connected": True})
        else:
            down_since = state.get("down_since") or now.isoformat()
            alerted = state.get("alerted", False)
            reason = "service unreachable" if status is None else status.get("state", "disconnected")
            if not alerted and now - datetime.fromisoformat(down_since) >= ALERT_AFTER:
                alerted = send_email(
                    _alert_emails(db),
                    f"[{pg_name(db)}] WhatsApp disconnected",
                    f"The WhatsApp bot has been disconnected since {down_since} ({reason}).\n\n"
                    "Rent reminders and alerts are paused until it's reconnected.\n"
                    "Open the dashboard → Messages to check the status or scan a new QR code.",
                )
            set_app_setting(
                db,
                "wa_health",
                {"connected": False, "down_since": down_since, "alerted": alerted, "reason": reason},
            )
        db.commit()


def catch_up() -> None:
    """Run on startup: queue anything that was due while the worker was down.

    Only within a few hours of the scheduled time, so a late restart doesn't
    send reminders at night. Dedupe keys prevent double-queueing.
    """
    generate_rent()
    now = now_ist()
    window = timedelta(hours=3)
    reminder_at = datetime.combine(now.date(), settings.reminder_at, tzinfo=settings.tz)
    if reminder_at <= now <= reminder_at + window:
        rent_reminders()
    report_at = datetime.combine(now.date(), settings.owner_report_at, tzinfo=settings.tz)
    if report_at <= now:  # the owner report can go any time later that day
        owner_report()
