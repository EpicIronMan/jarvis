#!/usr/bin/env python3
"""Hevy -> SQLite sync for LifeOS v2.

Pulls workouts from the Hevy API and writes them to workout_session +
workout_set tables. Idempotent: re-running upserts existing sessions by
hevy_id and replaces their set rows (handles edits in Hevy).

Usage:
    python3 /home/openclaw/lifeos/v2/ingest_hevy.py             # full backfill
    python3 /home/openclaw/lifeos/v2/ingest_hevy.py --since 2026-04-01
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

V2_DIR = Path(__file__).resolve().parent
DB_PATH = V2_DIR / "lifeos.db"
ET = ZoneInfo("America/Toronto")
ENV_PATH = "/opt/openclaw.env"
API_BASE = "https://api.hevyapp.com/v1"

KG_TO_LBS = 2.2046226218
M_TO_MILES = 0.0006213712

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ingest_hevy")


def read_api_key() -> str:
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith("HEVY_API_KEY="):
                return line[len("HEVY_API_KEY="):].rstrip("\n").strip()
    raise SystemExit("HEVY_API_KEY not found in /opt/openclaw.env")


def hevy_get(path: str, key: str) -> dict:
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"api-key": key, "accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def hevy_post(path: str, key: str, body: dict) -> dict:
    """POST to the Hevy API. Used for webhook subscription management."""
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=json.dumps(body).encode(),
        headers={"api-key": key, "accept": "application/json",
                 "content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def fetch_workout(hevy_id: str, key: str) -> dict:
    """Fetch a single workout by its Hevy id. Used by webhook handler."""
    data = hevy_get(f"/workouts/{hevy_id}", key)
    return data.get("workout", data)


def iso_to_et_date(iso_ts: str) -> str:
    """Convert an ISO timestamp to YYYY-MM-DD in America/Toronto."""
    if not iso_ts:
        return ""
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    return dt.astimezone(ET).date().isoformat()


def upsert_workout(con: sqlite3.Connection, w: dict) -> tuple[bool, int]:
    """Upsert one Hevy workout. Returns (created_new_session, set_count)."""
    hevy_id = w["id"]
    date_et = iso_to_et_date(w.get("start_time", ""))

    cur = con.execute("SELECT id FROM workout_session WHERE hevy_id = ?", (hevy_id,))
    row = cur.fetchone()
    if row:
        session_id = row[0]
        con.execute("DELETE FROM workout_set WHERE session_id = ?", (session_id,))
        con.execute(
            """UPDATE workout_session
               SET date=?, started_at=?, ended_at=?, title=?, notes=?,
                   source='HEVY', raw_payload=?
               WHERE id=?""",
            (date_et, w.get("start_time"), w.get("end_time"),
             w.get("title"), w.get("description"), json.dumps(w), session_id),
        )
        created = False
    else:
        cur = con.execute(
            """INSERT INTO workout_session
               (hevy_id, date, started_at, ended_at, title, notes, source, raw_payload)
               VALUES (?, ?, ?, ?, ?, ?, 'HEVY', ?)""",
            (hevy_id, date_et, w.get("start_time"), w.get("end_time"),
             w.get("title"), w.get("description"), json.dumps(w)),
        )
        session_id = cur.lastrowid
        created = True

    set_count = 0
    for ex in w.get("exercises", []):
        ex_title = ex.get("title", "Unknown")
        superset_id = ex.get("superset_id")
        for s in ex.get("sets", []):
            weight_kg = s.get("weight_kg")
            weight_lbs = round(weight_kg * KG_TO_LBS, 2) if weight_kg is not None else None
            distance_m = s.get("distance_meters")
            distance_mi = round(distance_m * M_TO_MILES, 4) if distance_m is not None else None
            con.execute(
                """INSERT INTO workout_set
                   (session_id, exercise, set_index, set_type, weight_lbs, reps,
                    rpe, distance_miles, duration_sec, superset_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, ex_title, (s.get("index") or 0) + 1,
                 s.get("type"), weight_lbs, s.get("reps"), s.get("rpe"),
                 distance_mi, s.get("duration_seconds"),
                 str(superset_id) if superset_id is not None else None),
            )
            set_count += 1

    return created, set_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="Only ingest workouts on/after this YYYY-MM-DD (ET)")
    ap.add_argument("--page-size", type=int, default=10, help="API page size (max 10)")
    args = ap.parse_args()

    key = read_api_key()
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")

    page = 1
    total_workouts = 0
    new_sessions = 0
    updated_sessions = 0
    total_sets = 0
    stop = False

    while not stop:
        data = hevy_get(f"/workouts?page={page}&pageSize={args.page_size}", key)
        workouts = data.get("workouts", [])
        if not workouts:
            break

        for w in workouts:
            date_et = iso_to_et_date(w.get("start_time", ""))
            if args.since and date_et < args.since:
                stop = True
                break
            created, n = upsert_workout(con, w)
            if created:
                new_sessions += 1
            else:
                updated_sessions += 1
            total_sets += n
            total_workouts += 1

        page_count = data.get("page_count", 1)
        log.info(f"page {page}/{page_count}: {len(workouts)} workouts processed")
        if page >= page_count:
            break
        page += 1

    con.commit()

    s = con.execute("SELECT COUNT(*) FROM workout_session WHERE source='HEVY'").fetchone()[0]
    t = con.execute(
        "SELECT COUNT(*) FROM workout_set ws JOIN workout_session s ON s.id=ws.session_id "
        "WHERE s.source='HEVY'"
    ).fetchone()[0]

    log.info(f"Hevy ingest done: processed {total_workouts} workouts "
             f"({new_sessions} new, {updated_sessions} updated), {total_sets} sets")
    log.info(f"Total HEVY sessions in DB: {s}, total HEVY sets: {t}")

    con.close()


if __name__ == "__main__":
    main()
