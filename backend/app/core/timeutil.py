"""Date helpers. All business dates are IST calendar dates."""

import calendar
from datetime import date, datetime, timedelta

from app.core.config import settings


def now_ist() -> datetime:
    return datetime.now(settings.tz)


def today_ist() -> date:
    return now_ist().date()


def month_start(d: date) -> date:
    return d.replace(day=1)


def days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def month_end(d: date) -> date:
    return d.replace(day=days_in_month(d))


def add_months(d: date, n: int) -> date:
    total = d.year * 12 + (d.month - 1) + n
    return date(total // 12, total % 12 + 1, 1)


def parse_month(value: str) -> date:
    """'2026-11' -> date(2026, 11, 1)"""
    year, month = value.split("-")[:2]
    return date(int(year), int(month), 1)


def month_label(d: date) -> str:
    return d.strftime("%b %Y")


def remaining_days(d: date) -> int:
    """Days from d to month end, inclusive of d."""
    return days_in_month(d) - d.day + 1


def prorate(amount: int, from_day: date) -> int:
    """Share of a monthly amount for the days from `from_day` to month end."""
    return round(amount * remaining_days(from_day) / days_in_month(from_day))


def end_of_day_ist(d: date) -> datetime:
    return datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=settings.tz)
