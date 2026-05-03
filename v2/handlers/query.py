"""Deterministic query helpers against lifeos.db.

Every function returns a plain dict (or list of dicts) that can be:
  - rendered directly as a CLI result,
  - handed to the model as structured context for prose,
  - compared in tests against golden values.

The model NEVER runs SQL and NEVER interprets raw sheet data. It only
sees the structured output of these functions.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from handlers.dates import today, yesterday


def connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def _to_list(rows) -> list[dict]:
    return [{k: r[k] for k in r.keys()} for r in rows]


# -------- body metrics (daily weight/BF from scale) --------

def latest_weight(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT * FROM body_metrics ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return _to_dict(row)


def weight_for_date(conn: sqlite3.Connection, date_str: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM body_metrics WHERE date = ?", (date_str,)
    ).fetchone()
    return _to_dict(row)


def weight_range(conn: sqlite3.Connection, start: str, end: str) -> dict:
    """Return per-day rows + summary stats across a date range."""
    rows = conn.execute(
        "SELECT * FROM body_metrics WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end),
    ).fetchall()
    days = _to_list(rows)
    if not days:
        return {"days": [], "n": 0, "min_weight": None, "max_weight": None,
                "start_weight": None, "end_weight": None, "change": None}
    weights = [d["weight_lbs"] for d in days if d.get("weight_lbs") is not None]
    return {
        "days": days,
        "n": len(days),
        "min_weight": min(weights) if weights else None,
        "max_weight": max(weights) if weights else None,
        "start_weight": days[0].get("weight_lbs"),
        "end_weight": days[-1].get("weight_lbs"),
        "change": round(days[-1]["weight_lbs"] - days[0]["weight_lbs"], 1)
            if days[0].get("weight_lbs") is not None and days[-1].get("weight_lbs") is not None else None,
    }


# -------- body scans (DEXA — authoritative BF%/lean mass) --------

def latest_body_scan(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT * FROM body_scan ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return _to_dict(row)


# -------- nutrition --------

def nutrition_for_date(conn: sqlite3.Connection, date_str: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM nutrition WHERE date = ?", (date_str,)
    ).fetchone()
    return _to_dict(row)


def nutrition_range_summary(conn: sqlite3.Connection, start: str, end: str) -> dict:
    """Return per-day rows + null-aware averages across the range.

    Bug #5 fix: only average over days that have non-null values. A week with
    3 missed days no longer drags the average down to ~30% of reality.
    """
    rows = conn.execute(
        "SELECT * FROM nutrition WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end),
    ).fetchall()
    days = _to_list(rows)
    if not days:
        return {"days": [], "avg_calories": None, "avg_protein_g": None,
                "n": 0, "n_with_calories": 0, "n_with_protein": 0}
    cal_vals = [d["calories"] for d in days if d.get("calories") is not None]
    prot_vals = [d["protein_g"] for d in days if d.get("protein_g") is not None]
    return {
        "days": days,
        "avg_calories": round(sum(cal_vals) / len(cal_vals), 1) if cal_vals else None,
        "avg_protein_g": round(sum(prot_vals) / len(prot_vals), 1) if prot_vals else None,
        "n": len(days),
        "n_with_calories": len(cal_vals),
        "n_with_protein": len(prot_vals),
    }


# -------- training (workout_session + workout_set) --------
#
# Source of truth is workout_session (parent) + workout_set (child, one row per set).
# These helpers aggregate per-exercise so the bot's coaching layer keeps the same
# scalar summary it had under the old workout table (sets/reps/weight_lbs/volume_lbs).

_EXERCISE_SUMMARY_SQL = """
    SELECT
        s.date            AS date,
        ws.exercise       AS exercise,
        s.title           AS session_type,
        s.source          AS source,
        COUNT(*)          AS sets,
        MAX(ws.reps)      AS reps,
        MAX(ws.weight_lbs) AS weight_lbs,
        MAX(ws.rpe)       AS rpe,
        COALESCE(SUM(COALESCE(ws.weight_lbs, 0) * COALESCE(ws.reps, 0)), 0) AS volume_lbs,
        MIN(ws.id)        AS first_set_id
    FROM workout_session s
    JOIN workout_set ws ON ws.session_id = s.id
"""


def _summarize_exercise_rows(rows) -> list[dict]:
    out = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        d.pop("first_set_id", None)
        out.append(d)
    return out


def training_on_date(conn: sqlite3.Connection, date_str: str) -> list[dict]:
    """Per-exercise summaries for a single date."""
    rows = conn.execute(
        _EXERCISE_SUMMARY_SQL +
        " WHERE s.date = ? GROUP BY s.id, ws.exercise ORDER BY first_set_id",
        (date_str,),
    ).fetchall()
    return _summarize_exercise_rows(rows)


def training_range(conn: sqlite3.Connection, start: str, end: str) -> dict:
    """Per-exercise summaries across a date range, plus session count."""
    rows = conn.execute(
        _EXERCISE_SUMMARY_SQL +
        " WHERE s.date BETWEEN ? AND ? GROUP BY s.id, ws.exercise "
        "ORDER BY s.date, first_set_id",
        (start, end),
    ).fetchall()
    exercises = _summarize_exercise_rows(rows)
    session_dates = sorted(set(e["date"] for e in exercises)) if exercises else []
    return {
        "exercises": exercises,
        "n_sessions": len(session_dates),
        "dates": session_dates,
        "n_exercises": len(exercises),
    }


def last_training_session(conn: sqlite3.Connection) -> dict:
    """Most recent training date and its per-exercise summaries."""
    row = conn.execute(
        "SELECT date FROM workout_session ORDER BY date DESC LIMIT 1"
    ).fetchone()
    if not row:
        return {"date": None, "exercises": []}
    return {"date": row["date"], "exercises": training_on_date(conn, row["date"])}


def last_session_of_exercise(conn: sqlite3.Connection, exercise: str) -> dict:
    """Most recent session containing `exercise`. Exact match first, then fuzzy."""
    row = conn.execute(
        "SELECT s.date AS date FROM workout_session s "
        "JOIN workout_set ws ON ws.session_id = s.id "
        "WHERE LOWER(ws.exercise) = LOWER(?) "
        "ORDER BY s.date DESC LIMIT 1",
        (exercise,),
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT s.date AS date FROM workout_session s "
            "JOIN workout_set ws ON ws.session_id = s.id "
            "WHERE LOWER(ws.exercise) LIKE '%' || LOWER(?) || '%' "
            "ORDER BY s.date DESC LIMIT 1",
            (exercise,),
        ).fetchone()
    if not row:
        return {"date": None, "exercises": [], "matched_exercise": None}

    date_str = row["date"]
    all_exercises = training_on_date(conn, date_str)
    matched = exercise
    for ex in all_exercises:
        if exercise.lower() in ex.get("exercise", "").lower():
            matched = ex["exercise"]
            break
    return {"date": date_str, "exercises": all_exercises, "matched_exercise": matched}


# -------- cardio --------

def cardio_on_date(conn: sqlite3.Connection, date_str: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM cardio WHERE date = ? ORDER BY id", (date_str,)
    ).fetchall()
    return _to_list(rows)


def cardio_recent(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM cardio ORDER BY date DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    return _to_list(rows)


# -------- recovery --------

def recovery_for_date(conn: sqlite3.Connection, date_str: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM recovery WHERE date = ?", (date_str,)
    ).fetchone()
    return _to_dict(row)


def recovery_range(conn: sqlite3.Connection, start: str, end: str) -> dict:
    """Return per-day rows + null-aware averages."""
    rows = conn.execute(
        "SELECT * FROM recovery WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end),
    ).fetchall()
    days = _to_list(rows)
    if not days:
        return {"days": [], "n": 0, "avg_sleep_hours": None, "avg_steps": None}
    sleep_vals = [d["sleep_hours"] for d in days if d.get("sleep_hours") is not None]
    step_vals = [d["steps"] for d in days if d.get("steps") is not None]
    return {
        "days": days,
        "n": len(days),
        "avg_sleep_hours": round(sum(sleep_vals) / len(sleep_vals), 1) if sleep_vals else None,
        "avg_steps": round(sum(step_vals) / len(step_vals)) if step_vals else None,
    }


# -------- omnibus 'stats' snapshot --------

def stats_snapshot(conn: sqlite3.Connection) -> dict:
    """Everything needed to answer 'my stats' — deterministic assembly.

    Bug #8 fix: for nutrition and recovery, tries today first, then falls
    back to the most recent row. At 6am before fitbit_sync has run, today's
    rows don't exist — we now return the latest available data instead of nulls.

    Intentionally returns structured data with explicit source labels:
      - latest_weight  : Body Metrics (Renpho/Fitbit scale, bioimpedance)
      - latest_body_scan: Body Scans (DEXA — AUTHORITATIVE for BF% and lean mass)
      - nutrition      : today if available, else most recent
      - recovery       : today if available, else most recent
      - last_training  : most recent logged session
    """
    today_str = today()

    # Nutrition: today, else most recent
    nut = nutrition_for_date(conn, today_str)
    nut_label = "today"
    if not nut:
        row = conn.execute(
            "SELECT * FROM nutrition ORDER BY date DESC LIMIT 1"
        ).fetchone()
        nut = _to_dict(row)
        nut_label = "most_recent"

    # Recovery: today, else most recent
    rec = recovery_for_date(conn, today_str)
    rec_label = "today"
    if not rec:
        row = conn.execute(
            "SELECT * FROM recovery ORDER BY date DESC LIMIT 1"
        ).fetchone()
        rec = _to_dict(row)
        rec_label = "most_recent"

    return {
        "latest_weight": latest_weight(conn),
        "latest_body_scan": latest_body_scan(conn),
        "nutrition": {"data": nut, "as_of": nut_label},
        "recovery": {"data": rec, "as_of": rec_label},
        "last_training": last_training_session(conn),
    }
