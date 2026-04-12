"""Deterministic date resolution for LifeOS v2.

The model NEVER decides what 'yesterday' means — this module does.
All public functions return ISO date strings (YYYY-MM-DD) in America/Toronto.

Per user memory `feedback_timezone.md`: always use America/Toronto (ET),
not UTC. This is a hard rule — every date-valued query in the bot flows
through here.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/Toronto")


# -------- current moment helpers --------

def now_et() -> datetime:
    return datetime.now(ET)


def today_et() -> date:
    return now_et().date()


def today() -> str:
    return today_et().isoformat()


def yesterday() -> str:
    return (today_et() - timedelta(days=1)).isoformat()


def days_ago(n: int) -> str:
    return (today_et() - timedelta(days=n)).isoformat()


# -------- token parsing --------

_WEEKDAYS = {
    "monday": 0,    "mon": 0,
    "tuesday": 1,   "tue": 1,  "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3,  "thu": 3,  "thur": 3, "thurs": 3,
    "friday": 4,    "fri": 4,
    "saturday": 5,  "sat": 5,
    "sunday": 6,    "sun": 6,
}

ISO_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def resolve_date(token: str | None) -> str | None:
    """Resolve a single date token to ISO YYYY-MM-DD, or None if unrecognized.

    Recognized (case-insensitive):
      - "today", "now"
      - "yesterday"
      - "N days ago" / "N day ago"
      - day-of-week name (returns the most recent past occurrence; today if match)
      - ISO YYYY-MM-DD (returned as-is after validation)
    """
    if token is None:
        return None
    t = token.strip().lower()
    if not t:
        return None

    m = ISO_DATE_RE.match(t)
    if m:
        return m.group(1)

    if t in ("today", "now"):
        return today()
    if t == "yesterday":
        return yesterday()

    m = re.match(r"^(\d+)\s+days?\s+ago$", t)
    if m:
        return days_ago(int(m.group(1)))

    if t in _WEEKDAYS:
        target_wd = _WEEKDAYS[t]
        today_d = today_et()
        days_back = (today_d.weekday() - target_wd) % 7
        return (today_d - timedelta(days=days_back)).isoformat()

    return None


def resolve_range(token: str | None) -> tuple[str, str] | None:
    """Resolve a range token to (start_iso, end_iso) inclusive, or None.

    Recognized:
      - "last N days" / "past N days"
      - "last week" / "past week" (= last 7 days ending today)
      - "last month" / "past month" (= last 30 days ending today)
      - "this week" (Monday of this week through today)
      - "this month" (1st of this month through today)
    """
    if token is None:
        return None
    t = token.strip().lower()
    if not t:
        return None

    today_d = today_et()

    m = re.match(r"^(?:last|past)\s+(\d+)\s+days?$", t)
    if m:
        n = int(m.group(1))
        start = today_d - timedelta(days=n - 1)
        return (start.isoformat(), today_d.isoformat())

    if t in ("last week", "past week"):
        return ((today_d - timedelta(days=6)).isoformat(), today_d.isoformat())

    if t in ("last month", "past month"):
        return ((today_d - timedelta(days=29)).isoformat(), today_d.isoformat())

    if t == "this week":
        monday = today_d - timedelta(days=today_d.weekday())
        return (monday.isoformat(), today_d.isoformat())

    if t == "this month":
        first = today_d.replace(day=1)
        return (first.isoformat(), today_d.isoformat())

    return None


def day_of_week(date_str: str) -> int:
    """Return 0=Monday .. 6=Sunday for an ISO date string."""
    return date.fromisoformat(date_str).weekday()
