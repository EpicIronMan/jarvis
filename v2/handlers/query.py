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


def weight_range(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM body_metrics WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end),
    ).fetchall()
    return _to_list(rows)


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
    """Return per-day rows + averages across the range."""
    rows = conn.execute(
        "SELECT * FROM nutrition WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end),
    ).fetchall()
    days = _to_list(rows)
    if not days:
        return {"days": [], "avg_calories": None, "avg_protein_g": None, "n": 0}
    n = len(days)
    avg_cal = sum((d["calories"] or 0) for d in days) / n
    avg_p = sum((d["protein_g"] or 0) for d in days) / n
    return {
        "days": days,
        "avg_calories": round(avg_cal, 1),
        "avg_protein_g": round(avg_p, 1),
        "n": n,
    }


# -------- training (workout) --------

def training_on_date(conn: sqlite3.Connection, date_str: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM workout WHERE date = ? ORDER BY id", (date_str,)
    ).fetchall()
    return _to_list(rows)


def training_range(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM workout WHERE date BETWEEN ? AND ? ORDER BY date, id",
        (start, end),
    ).fetchall()
    return _to_list(rows)


def last_training_session(conn: sqlite3.Connection) -> dict:
    """Return all workout rows from the most recent date any exercise was logged."""
    row = conn.execute(
        "SELECT date FROM workout ORDER BY date DESC LIMIT 1"
    ).fetchone()
    if not row:
        return {"date": None, "exercises": []}
    date_str = row["date"]
    return {
        "date": date_str,
        "exercises": training_on_date(conn, date_str),
    }


def last_session_of_exercise(conn: sqlite3.Connection, exercise: str) -> dict:
    """Return the most recent session containing `exercise` (case-insensitive match).

    Returns the whole session (all exercises from that date), not just the
    matching exercise — context matters for "how did it go last time."
    """
    row = conn.execute(
        "SELECT date FROM workout WHERE LOWER(exercise) = LOWER(?) "
        "ORDER BY date DESC LIMIT 1",
        (exercise,),
    ).fetchone()
    if not row:
        return {"date": None, "exercises": []}
    date_str = row["date"]
    return {"date": date_str, "exercises": training_on_date(conn, date_str)}


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


def recovery_range(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM recovery WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end),
    ).fetchall()
    return _to_list(rows)


# -------- omnibus 'stats' snapshot --------

def stats_snapshot(conn: sqlite3.Connection) -> dict:
    """Everything needed to answer 'my stats' — deterministic assembly.

    Intentionally returns structured data with explicit source labels:
      - latest_weight  : Body Metrics (Renpho/Fitbit scale, bioimpedance)
      - latest_body_scan: Body Scans (DEXA — AUTHORITATIVE for BF% and lean mass)
      - today_nutrition: Nutrition for today in ET
      - today_recovery : Recovery for today in ET
      - last_training  : most recent logged session
    """
    return {
        "latest_weight": latest_weight(conn),
        "latest_body_scan": latest_body_scan(conn),
        "today_nutrition": nutrition_for_date(conn, today()),
        "today_recovery": recovery_for_date(conn, today()),
        "last_training": last_training_session(conn),
    }
