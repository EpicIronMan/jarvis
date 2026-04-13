"""Tests for deterministic date resolution."""

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handlers.dates import resolve_date, resolve_range, today_et, ET


# Fix "today" to 2026-04-12 (Saturday) for deterministic tests
FIXED_TODAY = date(2026, 4, 12)


def _mock_today_et():
    return FIXED_TODAY


class TestResolveDate:
    @patch("handlers.dates.today_et", _mock_today_et)
    def test_today(self):
        assert resolve_date("today") == "2026-04-12"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_now(self):
        assert resolve_date("now") == "2026-04-12"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_yesterday(self):
        assert resolve_date("yesterday") == "2026-04-11"

    def test_iso(self):
        assert resolve_date("2026-04-09") == "2026-04-09"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_3_days_ago(self):
        assert resolve_date("3 days ago") == "2026-04-09"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_1_day_ago(self):
        assert resolve_date("1 day ago") == "2026-04-11"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_monday(self):
        # 2026-04-12 is Sunday. Most recent Monday = 2026-04-06
        assert resolve_date("monday") == "2026-04-06"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_sunday_is_today(self):
        # 2026-04-12 is Sunday. "sunday" = today
        assert resolve_date("sunday") == "2026-04-12"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_saturday(self):
        # 2026-04-12 is Sunday. Most recent Saturday = 2026-04-11
        assert resolve_date("saturday") == "2026-04-11"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_fri_abbreviation(self):
        # 2026-04-12 is Sunday. Most recent Friday = 2026-04-10
        assert resolve_date("fri") == "2026-04-10"

    def test_none(self):
        assert resolve_date(None) is None

    def test_empty(self):
        assert resolve_date("") is None

    def test_gibberish(self):
        assert resolve_date("foobar") is None

    def test_case_insensitive(self):
        assert resolve_date("TODAY") is not None
        assert resolve_date("Yesterday") is not None
        assert resolve_date("MONDAY") is not None


class TestResolveRange:
    @patch("handlers.dates.today_et", _mock_today_et)
    def test_last_7_days(self):
        start, end = resolve_range("last 7 days")
        assert end == "2026-04-12"
        assert start == "2026-04-06"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_past_3_days(self):
        start, end = resolve_range("past 3 days")
        assert end == "2026-04-12"
        assert start == "2026-04-10"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_last_week(self):
        start, end = resolve_range("last week")
        assert end == "2026-04-12"
        assert start == "2026-04-06"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_this_week(self):
        # Sunday Apr 12. Monday of this week = Apr 06
        start, end = resolve_range("this week")
        assert start == "2026-04-06"
        assert end == "2026-04-12"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_this_month(self):
        start, end = resolve_range("this month")
        assert start == "2026-04-01"
        assert end == "2026-04-12"

    @patch("handlers.dates.today_et", _mock_today_et)
    def test_last_month(self):
        start, end = resolve_range("last month")
        assert end == "2026-04-12"
        assert start == "2026-03-14"

    def test_none(self):
        assert resolve_range(None) is None

    def test_empty(self):
        assert resolve_range("") is None

    def test_gibberish(self):
        assert resolve_range("foobar") is None
