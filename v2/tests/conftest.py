"""Shared fixtures for v2 tests.

Creates an in-memory SQLite DB from schema.sql and seeds it with known
test data so query tests are deterministic and don't touch lifeos.db.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

V2_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_DIR))


@pytest.fixture
def conn():
    """In-memory SQLite connection with schema applied and test data seeded."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row

    # Apply schema — use executescript which handles multi-statement SQL properly.
    # Strip the WAL pragma since it's not valid for :memory:.
    schema = (V2_DIR / "schema.sql").read_text()
    schema = schema.replace("PRAGMA journal_mode = WAL;", "")
    db.executescript(schema)

    # Seed test data
    _seed(db)
    db.commit()
    yield db
    db.close()


def _seed(db: sqlite3.Connection):
    """Insert known rows for deterministic testing."""

    # Body metrics — 5 days
    for i, (d, w, bf) in enumerate([
        ("2026-04-07", 174.0, 22.0),
        ("2026-04-08", 173.5, 21.8),
        ("2026-04-09", 173.0, 21.5),
        ("2026-04-10", 172.5, 21.2),
        ("2026-04-11", 172.0, 21.0),
    ]):
        db.execute(
            "INSERT INTO body_metrics (date, weight_lbs, weight_kg, body_fat_pct, bmi, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (d, w, round(w / 2.205, 1), bf, round(w / (70 * 70) * 703, 2), "FITBIT"),
        )

    # Body scan — 1 DEXA
    db.execute(
        "INSERT INTO body_scan (date, scan_type, total_bf_pct, lean_mass_lbs, lean_mass_kg, "
        "bone_density, visceral_fat_area, trunk_fat_pct, arms_fat_pct, legs_fat_pct, "
        "rmr_cal, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2026-04-02", "DEXA", 26.3, 128.6, 58.3, 1.264, 71.05, 31.3, 20.7, 22.6, 1618.0, "DEXA"),
    )

    # Nutrition — 4 days, one with NULL calories
    for d, cal, prot in [
        ("2026-04-08", 2100.0, 165.0),
        ("2026-04-09", 2200.0, 170.0),
        ("2026-04-10", None, None),  # missed day
        ("2026-04-11", 1950.0, 155.0),
    ]:
        db.execute(
            "INSERT INTO nutrition (date, calories, protein_g, source) VALUES (?, ?, ?, ?)",
            (d, cal, prot, "FITBIT"),
        )

    # Workouts — 2 sessions
    workouts = [
        ("2026-04-09", "Lat Pulldown", 3, 10, 120.0, None, 3600.0, "BACK", "TELEGRAM"),
        ("2026-04-09", "Seated Row Machine", 3, 10, 100.0, None, 3000.0, "BACK", "TELEGRAM"),
        ("2026-04-09", "Pull Ups", 3, 8, 0.0, None, 0.0, "BACK", "TELEGRAM"),
        ("2026-04-11", "Seated Leg Press", 3, 10, 320.0, None, 9600.0, "LEGS", "TELEGRAM"),
        ("2026-04-11", "Leg Extension", 3, 12, 90.0, None, 3240.0, "LEGS", "TELEGRAM"),
        ("2026-04-11", "Bench Press", 3, 8, 185.0, 8.0, 4440.0, "CHEST", "TELEGRAM"),
    ]
    for d, ex, s, r, w, rpe, vol, st, src in workouts:
        db.execute(
            "INSERT INTO workout (date, exercise, sets, reps, weight_lbs, rpe, volume_lbs, "
            "session_type, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d, ex, s, r, w, rpe, vol, st, src),
        )

    # Cardio — 1 session
    db.execute(
        "INSERT INTO cardio (date, exercise, duration_min, speed, incline, net_calories, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-04-10", "Treadmill", 30.0, 3.5, 5.0, 250.0, "FITBIT"),
    )

    # Recovery — 4 days, one with NULL sleep
    for d, eff, slp, steps, active, rhr in [
        ("2026-04-08", 88.0, 7.2, 8500, 45, 62),
        ("2026-04-09", 91.0, 7.8, 10200, 60, 60),
        ("2026-04-10", None, None, 5600, 20, 64),  # no sleep data
        ("2026-04-11", 85.0, 6.5, 9800, 55, 61),
    ]:
        db.execute(
            "INSERT INTO recovery (date, efficiency_pct, sleep_hours, steps, active_minutes, "
            "resting_hr, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (d, eff, slp, steps, active, rhr, "FITBIT"),
        )
