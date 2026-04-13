"""Write handlers for LifeOS v2 — all INSERT/UPDATE operations against lifeos.db.

Every write:
  1. Validates input
  2. Writes to SQLite
  3. Appends an event to the events table for audit
  4. Returns a structured confirmation dict

The model NEVER writes SQL directly. It only sees the confirmation output.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from handlers.dates import today, now_et

ET = ZoneInfo("America/Toronto")


def _log_event(conn: sqlite3.Connection, kind: str, payload: dict, msg_id: str | None = None):
    """Append an audit event."""
    conn.execute(
        "INSERT INTO events (ts, kind, payload_json, user_msg_id) VALUES (?, ?, ?, ?)",
        (datetime.now(ET).isoformat(), kind, json.dumps(payload), msg_id),
    )


def log_weight(
    conn: sqlite3.Connection,
    weight_lbs: float,
    body_fat_pct: float | None = None,
    source: str = "TELEGRAM",
    notes: str = "",
    date_str: str | None = None,
) -> dict:
    """Log a body weight entry. Upserts on date."""
    d = date_str or today()
    kg = round(weight_lbs / 2.20462, 1)
    bmi = round(weight_lbs / (67.5 ** 2) * 703, 2)  # height from user_facts ideally

    # Try to get height from user_facts for accurate BMI
    row = conn.execute("SELECT value FROM user_facts WHERE key = 'height_cm'").fetchone()
    if row:
        height_cm = float(row[0])
        height_in = height_cm / 2.54
        bmi = round(weight_lbs / (height_in ** 2) * 703, 2)

    conn.execute(
        "INSERT INTO body_metrics (date, weight_lbs, weight_kg, body_fat_pct, bmi, source, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(date) DO UPDATE SET "
        "weight_lbs=excluded.weight_lbs, weight_kg=excluded.weight_kg, "
        "body_fat_pct=COALESCE(excluded.body_fat_pct, body_metrics.body_fat_pct), "
        "bmi=excluded.bmi, source=excluded.source, "
        "notes=CASE WHEN excluded.notes != '' THEN excluded.notes ELSE body_metrics.notes END",
        (d, weight_lbs, kg, body_fat_pct, bmi, source, notes),
    )
    _log_event(conn, "handler_call", {
        "handler": "log_weight", "date": d, "weight_lbs": weight_lbs, "source": source,
    })
    conn.commit()
    return {"action": "log_weight", "date": d, "weight_lbs": weight_lbs, "weight_kg": kg, "bmi": bmi}


def log_workout(
    conn: sqlite3.Connection,
    exercises: list[dict],
    session_type: str = "BRO_SPLIT",
    source: str = "TELEGRAM",
    date_str: str | None = None,
) -> dict:
    """Log workout exercises. Each exercise dict: {name, sets, reps, weight_lbs, rpe?}.

    Returns summary with total volume.
    """
    d = date_str or today()
    logged = []
    total_volume = 0

    for ex in exercises:
        name = ex["name"]
        sets = int(ex["sets"])
        reps = int(ex["reps"])
        weight = float(ex["weight_lbs"])
        rpe = ex.get("rpe")
        volume = sets * reps * weight
        total_volume += volume

        conn.execute(
            "INSERT INTO workout (date, exercise, sets, reps, weight_lbs, rpe, volume_lbs, session_type, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d, name, sets, reps, weight, rpe, volume, session_type, source),
        )
        logged.append({"exercise": name, "sets": sets, "reps": reps, "weight_lbs": weight, "volume": volume})

    _log_event(conn, "handler_call", {
        "handler": "log_workout", "date": d, "n_exercises": len(exercises),
        "total_volume": total_volume, "session_type": session_type,
    })
    conn.commit()
    return {
        "action": "log_workout", "date": d, "exercises": logged,
        "total_volume": total_volume, "session_type": session_type,
    }


def log_nutrition(
    conn: sqlite3.Connection,
    calories: float,
    protein_g: float,
    carbs_g: float | None = None,
    fat_g: float | None = None,
    fiber_g: float | None = None,
    sodium_mg: float | None = None,
    source: str = "TELEGRAM",
    notes: str = "",
    date_str: str | None = None,
) -> dict:
    """Log daily nutrition. Upserts on date."""
    d = date_str or today()
    conn.execute(
        "INSERT INTO nutrition (date, calories, protein_g, carbs_g, fat_g, fiber_g, sodium_mg, source, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(date) DO UPDATE SET "
        "calories=excluded.calories, protein_g=excluded.protein_g, "
        "carbs_g=COALESCE(excluded.carbs_g, nutrition.carbs_g), "
        "fat_g=COALESCE(excluded.fat_g, nutrition.fat_g), "
        "fiber_g=COALESCE(excluded.fiber_g, nutrition.fiber_g), "
        "sodium_mg=COALESCE(excluded.sodium_mg, nutrition.sodium_mg), "
        "source=excluded.source, "
        "notes=CASE WHEN excluded.notes != '' THEN excluded.notes ELSE nutrition.notes END",
        (d, calories, protein_g, carbs_g, fat_g, fiber_g, sodium_mg, source, notes),
    )
    _log_event(conn, "handler_call", {
        "handler": "log_nutrition", "date": d, "calories": calories, "protein_g": protein_g,
    })
    conn.commit()
    return {"action": "log_nutrition", "date": d, "calories": calories, "protein_g": protein_g}


def log_cardio(
    conn: sqlite3.Connection,
    exercise: str,
    duration_min: float,
    net_calories: float,
    met_used: float | None = None,
    speed: float | None = None,
    incline: float | None = None,
    source: str = "TELEGRAM",
    notes: str = "",
    date_str: str | None = None,
) -> dict:
    """Log a cardio session."""
    d = date_str or today()
    conn.execute(
        "INSERT INTO cardio (date, exercise, duration_min, speed, incline, net_calories, met_used, source, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (d, exercise, duration_min, speed, incline, net_calories, met_used, source, notes),
    )
    _log_event(conn, "handler_call", {
        "handler": "log_cardio", "date": d, "exercise": exercise,
        "duration_min": duration_min, "net_calories": net_calories,
    })
    conn.commit()
    return {"action": "log_cardio", "date": d, "exercise": exercise, "duration_min": duration_min, "net_calories": net_calories}


def log_body_scan(
    conn: sqlite3.Connection,
    scan_type: str,
    total_bf_pct: float,
    lean_mass_lbs: float | None = None,
    lean_mass_kg: float | None = None,
    bone_density: float | None = None,
    visceral_fat_area: float | None = None,
    trunk_fat_pct: float | None = None,
    arms_fat_pct: float | None = None,
    legs_fat_pct: float | None = None,
    rmr_cal: float | None = None,
    source: str = "DEXA",
    source_file: str | None = None,
    notes: str = "",
    date_str: str | None = None,
) -> dict:
    """Log a body scan (DEXA, InBody, etc). Upserts on date."""
    d = date_str or today()

    # Compute lean mass in both units if only one provided
    if lean_mass_lbs and not lean_mass_kg:
        lean_mass_kg = round(lean_mass_lbs / 2.20462, 1)
    elif lean_mass_kg and not lean_mass_lbs:
        lean_mass_lbs = round(lean_mass_kg * 2.20462, 1)

    conn.execute(
        "INSERT INTO body_scan (date, scan_type, total_bf_pct, lean_mass_lbs, lean_mass_kg, "
        "bone_density, visceral_fat_area, trunk_fat_pct, arms_fat_pct, legs_fat_pct, "
        "rmr_cal, source, source_file, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(date) DO UPDATE SET "
        "scan_type=excluded.scan_type, total_bf_pct=excluded.total_bf_pct, "
        "lean_mass_lbs=excluded.lean_mass_lbs, lean_mass_kg=excluded.lean_mass_kg, "
        "bone_density=COALESCE(excluded.bone_density, body_scan.bone_density), "
        "visceral_fat_area=COALESCE(excluded.visceral_fat_area, body_scan.visceral_fat_area), "
        "trunk_fat_pct=COALESCE(excluded.trunk_fat_pct, body_scan.trunk_fat_pct), "
        "arms_fat_pct=COALESCE(excluded.arms_fat_pct, body_scan.arms_fat_pct), "
        "legs_fat_pct=COALESCE(excluded.legs_fat_pct, body_scan.legs_fat_pct), "
        "rmr_cal=COALESCE(excluded.rmr_cal, body_scan.rmr_cal), "
        "source=excluded.source, source_file=excluded.source_file, "
        "notes=CASE WHEN excluded.notes != '' THEN excluded.notes ELSE body_scan.notes END",
        (d, scan_type, total_bf_pct, lean_mass_lbs, lean_mass_kg,
         bone_density, visceral_fat_area, trunk_fat_pct, arms_fat_pct, legs_fat_pct,
         rmr_cal, source, source_file, notes),
    )
    _log_event(conn, "handler_call", {
        "handler": "log_body_scan", "date": d, "scan_type": scan_type,
        "total_bf_pct": total_bf_pct,
    })
    conn.commit()
    return {"action": "log_body_scan", "date": d, "scan_type": scan_type, "total_bf_pct": total_bf_pct}


def rename_exercise(
    conn: sqlite3.Connection,
    old_name: str,
    new_name: str,
) -> dict:
    """Rename an exercise across all workout rows (case-insensitive match on old_name)."""
    cursor = conn.execute(
        "UPDATE workout SET exercise = ? WHERE LOWER(exercise) = LOWER(?)",
        (new_name, old_name),
    )
    count = cursor.rowcount
    _log_event(conn, "handler_call", {
        "handler": "rename_exercise", "old_name": old_name, "new_name": new_name,
        "rows_updated": count,
    })
    conn.commit()
    return {"action": "rename_exercise", "old_name": old_name, "new_name": new_name, "rows_updated": count}


def edit_weight(
    conn: sqlite3.Connection,
    date_str: str,
    weight_lbs: float,
    notes: str = "manual edit",
) -> dict:
    """Edit a weight entry for a specific date."""
    kg = round(weight_lbs / 2.20462, 1)
    cursor = conn.execute(
        "UPDATE body_metrics SET weight_lbs = ?, weight_kg = ?, notes = ? WHERE date = ?",
        (weight_lbs, kg, notes, date_str),
    )
    if cursor.rowcount == 0:
        return {"action": "edit_weight", "date": date_str, "error": "no row found for that date"}
    _log_event(conn, "handler_call", {
        "handler": "edit_weight", "date": date_str, "weight_lbs": weight_lbs,
    })
    conn.commit()
    return {"action": "edit_weight", "date": date_str, "weight_lbs": weight_lbs, "weight_kg": kg}


def delete_workout(
    conn: sqlite3.Connection,
    workout_id: int,
) -> dict:
    """Delete a specific workout row by ID."""
    row = conn.execute("SELECT * FROM workout WHERE id = ?", (workout_id,)).fetchone()
    if not row:
        return {"action": "delete_workout", "id": workout_id, "error": "not found"}
    conn.execute("DELETE FROM workout WHERE id = ?", (workout_id,))
    _log_event(conn, "handler_call", {
        "handler": "delete_workout", "id": workout_id,
        "exercise": row["exercise"], "date": row["date"],
    })
    conn.commit()
    return {"action": "delete_workout", "id": workout_id, "exercise": row["exercise"], "date": row["date"]}


def log_recovery(
    conn: sqlite3.Connection,
    date_str: str,
    efficiency_pct: float | None = None,
    sleep_hours: float | None = None,
    steps: int | None = None,
    active_minutes: int | None = None,
    resting_hr: int | None = None,
    sleep_score_computed: float | None = None,
    time_in_bed_h: float | None = None,
    source: str = "FITBIT",
    notes: str = "",
) -> dict:
    """Log/upsert a recovery row. Preserves existing non-null values on partial updates.

    This is the fix for the v1 fitbit_sync partial-update overwrite bug:
    if a field is None in this call but has a value in the DB, the DB value is kept.
    """
    conn.execute(
        "INSERT INTO recovery (date, efficiency_pct, sleep_hours, steps, active_minutes, "
        "resting_hr, sleep_score_computed, time_in_bed_h, source, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(date) DO UPDATE SET "
        "efficiency_pct=COALESCE(excluded.efficiency_pct, recovery.efficiency_pct), "
        "sleep_hours=COALESCE(excluded.sleep_hours, recovery.sleep_hours), "
        "steps=COALESCE(excluded.steps, recovery.steps), "
        "active_minutes=COALESCE(excluded.active_minutes, recovery.active_minutes), "
        "resting_hr=COALESCE(excluded.resting_hr, recovery.resting_hr), "
        "sleep_score_computed=COALESCE(excluded.sleep_score_computed, recovery.sleep_score_computed), "
        "time_in_bed_h=COALESCE(excluded.time_in_bed_h, recovery.time_in_bed_h), "
        "source=excluded.source, "
        "notes=CASE WHEN excluded.notes != '' THEN excluded.notes ELSE recovery.notes END",
        (date_str, efficiency_pct, sleep_hours, steps, active_minutes,
         resting_hr, sleep_score_computed, time_in_bed_h, source, notes),
    )
    _log_event(conn, "handler_call", {
        "handler": "log_recovery", "date": date_str, "source": source,
    })
    conn.commit()
    return {"action": "log_recovery", "date": date_str, "source": source}
