#!/usr/bin/env python3
"""
Migration 001 — workout → workout_session + workout_set (per-set schema).

One-shot. Idempotent: re-running is a no-op once schema_version=2 is recorded.
Backfills the existing workout rows into the new tables, preserving order.
Old `workout` table is retained for Phase 3 handler cutover.
"""
import os, sys, sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("LIFEOS_DIR", "/home/openclaw/lifeos")) / "v2" / "lifeos.db"
SCHEMA  = Path(__file__).parent.parent / "schema.sql"


def main():
    if not DB_PATH.exists():
        sys.exit(f"DB not found at {DB_PATH}")

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")

    cur = con.execute("SELECT MAX(version) FROM schema_version")
    current_version = cur.fetchone()[0] or 0
    if current_version >= 2:
        print(f"schema_version already {current_version}, no migration needed")
        return

    with open(SCHEMA) as f:
        con.executescript(f.read())

    existing = con.execute("SELECT COUNT(*) FROM workout_session").fetchone()[0]
    if existing > 0:
        print(f"workout_session already has {existing} rows, skipping backfill")
        con.commit()
        return

    rows = con.execute("""
        SELECT id, date, exercise, sets, reps, weight_lbs, rpe, session_type, source, notes
        FROM workout
        ORDER BY date, id
    """).fetchall()

    sessions_created = 0
    sets_created = 0
    session_id_by_key = {}
    next_set_index = {}

    for (wid, date, exercise, sets_n, reps, weight, rpe, session_type, source, notes) in rows:
        key = (date, session_type or "")
        if key not in session_id_by_key:
            cur = con.execute(
                "INSERT INTO workout_session (date, title, source, notes) "
                "VALUES (?, ?, 'BACKFILL', ?)",
                (date, session_type, f"backfilled from workout table on 2026-05-03"),
            )
            session_id_by_key[key] = cur.lastrowid
            sessions_created += 1

        sid = session_id_by_key[key]
        idx_key = (sid, exercise)
        start_idx = next_set_index.get(idx_key, 0)

        for i in range(sets_n):
            con.execute(
                "INSERT INTO workout_set "
                "(session_id, exercise, set_index, set_type, weight_lbs, reps, rpe) "
                "VALUES (?, ?, ?, 'normal', ?, ?, ?)",
                (sid, exercise, start_idx + i + 1, weight, reps, rpe),
            )
            sets_created += 1

        next_set_index[idx_key] = start_idx + sets_n

    con.commit()
    print(f"Backfill complete: {sessions_created} sessions, {sets_created} sets")

    s = con.execute("SELECT COUNT(*) FROM workout_session").fetchone()[0]
    t = con.execute("SELECT COUNT(*) FROM workout_set").fetchone()[0]
    print(f"workout_session count: {s}")
    print(f"workout_set count:     {t}")

    con.close()


if __name__ == "__main__":
    main()
