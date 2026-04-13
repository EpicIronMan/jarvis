"""Tests for query helpers — uses in-memory DB seeded by conftest.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handlers import query


class TestWeight:
    def test_latest_weight(self, conn):
        r = query.latest_weight(conn)
        assert r is not None
        assert r["date"] == "2026-04-11"
        assert r["weight_lbs"] == 172.0

    def test_weight_for_date(self, conn):
        r = query.weight_for_date(conn, "2026-04-09")
        assert r is not None
        assert r["weight_lbs"] == 173.0

    def test_weight_for_date_missing(self, conn):
        r = query.weight_for_date(conn, "2025-01-01")
        assert r is None

    def test_weight_range(self, conn):
        r = query.weight_range(conn, "2026-04-08", "2026-04-11")
        assert r["n"] == 4
        assert r["start_weight"] == 173.5
        assert r["end_weight"] == 172.0
        assert r["change"] == -1.5
        assert r["min_weight"] == 172.0
        assert r["max_weight"] == 173.5

    def test_weight_range_empty(self, conn):
        r = query.weight_range(conn, "2025-01-01", "2025-01-07")
        assert r["n"] == 0
        assert r["change"] is None


class TestBodyScan:
    def test_latest_body_scan(self, conn):
        r = query.latest_body_scan(conn)
        assert r is not None
        assert r["scan_type"] == "DEXA"
        assert r["total_bf_pct"] == 26.3


class TestNutrition:
    def test_nutrition_for_date(self, conn):
        r = query.nutrition_for_date(conn, "2026-04-09")
        assert r is not None
        assert r["calories"] == 2200.0
        assert r["protein_g"] == 170.0

    def test_nutrition_for_date_missing(self, conn):
        r = query.nutrition_for_date(conn, "2025-01-01")
        assert r is None

    def test_nutrition_range_summary_null_aware(self, conn):
        """Bug #5: null days must not drag averages down."""
        r = query.nutrition_range_summary(conn, "2026-04-08", "2026-04-11")
        assert r["n"] == 4  # 4 rows exist
        assert r["n_with_calories"] == 3  # only 3 have non-null calories
        assert r["n_with_protein"] == 3
        # Average should be over 3 days, not 4
        expected_avg_cal = round((2100 + 2200 + 1950) / 3, 1)
        assert r["avg_calories"] == expected_avg_cal
        expected_avg_prot = round((165 + 170 + 155) / 3, 1)
        assert r["avg_protein_g"] == expected_avg_prot

    def test_nutrition_range_empty(self, conn):
        r = query.nutrition_range_summary(conn, "2025-01-01", "2025-01-07")
        assert r["n"] == 0
        assert r["avg_calories"] is None


class TestTraining:
    def test_training_on_date(self, conn):
        r = query.training_on_date(conn, "2026-04-09")
        assert len(r) == 3
        exercises = [e["exercise"] for e in r]
        assert "Lat Pulldown" in exercises
        assert "Pull Ups" in exercises

    def test_training_on_date_empty(self, conn):
        r = query.training_on_date(conn, "2026-04-07")
        assert r == []

    def test_last_training_session(self, conn):
        r = query.last_training_session(conn)
        assert r["date"] == "2026-04-11"
        assert len(r["exercises"]) == 3  # Seated Leg Press, Leg Extension, Bench Press

    def test_training_range(self, conn):
        r = query.training_range(conn, "2026-04-07", "2026-04-11")
        assert r["n_sessions"] == 2  # Apr 9 and Apr 11
        assert r["n_exercises"] == 6
        assert "2026-04-09" in r["dates"]
        assert "2026-04-11" in r["dates"]


class TestExerciseFuzzyMatch:
    """Bug #4: fuzzy match for exercise names."""

    def test_exact_match(self, conn):
        r = query.last_session_of_exercise(conn, "Bench Press")
        assert r["date"] == "2026-04-11"
        assert r["matched_exercise"] == "Bench Press"

    def test_case_insensitive(self, conn):
        r = query.last_session_of_exercise(conn, "bench press")
        assert r["date"] == "2026-04-11"

    def test_fuzzy_partial_match(self, conn):
        """'bench' should match 'Bench Press'."""
        r = query.last_session_of_exercise(conn, "bench")
        assert r["date"] == "2026-04-11"
        assert r["matched_exercise"] == "Bench Press"

    def test_fuzzy_leg_press(self, conn):
        """'leg press' should match 'Seated Leg Press' or 'Leg Press'."""
        r = query.last_session_of_exercise(conn, "leg press")
        assert r["date"] is not None
        assert "Leg Press" in r["matched_exercise"]

    def test_fuzzy_pulldown(self, conn):
        r = query.last_session_of_exercise(conn, "pulldown")
        assert r["date"] == "2026-04-09"
        assert "Pulldown" in r["matched_exercise"]

    def test_no_match(self, conn):
        r = query.last_session_of_exercise(conn, "deadlift")
        assert r["date"] is None
        assert r["exercises"] == []


class TestCardio:
    def test_cardio_on_date(self, conn):
        r = query.cardio_on_date(conn, "2026-04-10")
        assert len(r) == 1
        assert r[0]["exercise"] == "Treadmill"

    def test_cardio_on_date_empty(self, conn):
        r = query.cardio_on_date(conn, "2026-04-07")
        assert r == []

    def test_cardio_recent(self, conn):
        r = query.cardio_recent(conn)
        assert len(r) == 1


class TestRecovery:
    def test_recovery_for_date(self, conn):
        r = query.recovery_for_date(conn, "2026-04-09")
        assert r is not None
        assert r["sleep_hours"] == 7.8
        assert r["steps"] == 10200

    def test_recovery_range_null_aware(self, conn):
        r = query.recovery_range(conn, "2026-04-08", "2026-04-11")
        assert r["n"] == 4
        # Only 3 days have sleep data
        expected_avg_sleep = round((7.2 + 7.8 + 6.5) / 3, 1)
        assert r["avg_sleep_hours"] == expected_avg_sleep
        # All 4 days have steps
        expected_avg_steps = round((8500 + 10200 + 5600 + 9800) / 4)
        assert r["avg_steps"] == expected_avg_steps


class TestStatsSnapshot:
    """Bug #8: stats_snapshot falls back to most-recent when today has no data."""

    def test_stats_with_today_data(self, conn):
        """When today's data exists, use it."""
        from unittest.mock import patch
        with patch("handlers.query.today", return_value="2026-04-11"):
            r = query.stats_snapshot(conn)
        assert r["nutrition"]["as_of"] == "today"
        assert r["nutrition"]["data"]["calories"] == 1950.0
        assert r["recovery"]["as_of"] == "today"
        assert r["recovery"]["data"]["steps"] == 9800

    def test_stats_fallback_when_today_missing(self, conn):
        """When today has no data, fall back to most recent."""
        from unittest.mock import patch
        with patch("handlers.query.today", return_value="2026-04-12"):
            r = query.stats_snapshot(conn)
        # No data for Apr 12 — should fall back
        assert r["nutrition"]["as_of"] == "most_recent"
        assert r["nutrition"]["data"]["date"] == "2026-04-11"
        assert r["recovery"]["as_of"] == "most_recent"
        assert r["recovery"]["data"]["date"] == "2026-04-11"

    def test_stats_always_has_weight_and_scan(self, conn):
        from unittest.mock import patch
        with patch("handlers.query.today", return_value="2026-04-12"):
            r = query.stats_snapshot(conn)
        assert r["latest_weight"] is not None
        assert r["latest_body_scan"] is not None
        assert r["last_training"]["date"] == "2026-04-11"
