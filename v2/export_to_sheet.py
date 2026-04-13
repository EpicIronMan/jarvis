#!/usr/bin/env python3
"""One-way SQLite → Google Sheet push for LifeOS v2.

Exports all data from lifeos.db to the read-only Google Sheet view via gog CLI.
The sheet becomes a read-only mirror — all writes go through SQLite.

Usage:
    python3 /home/openclaw/lifeos/v2/export_to_sheet.py [--full]

Without --full, only exports rows from the last 7 days (incremental).
With --full, exports everything (for initial setup or recovery).
"""

import json
import logging
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

V2_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(V2_DIR))

from handlers.query import connect

DB_PATH = V2_DIR / "lifeos.db"
LOG_PATH = V2_DIR / "export.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("export_to_sheet")

SHEET_ID = os.environ.get("SHEET_ID", "")
GOG = os.environ.get("GOG_PATH", "/usr/local/bin/gog")
GOG_ACCOUNT = os.environ.get("GOG_ACCOUNT", "")


def _gog_env():
    return {
        **os.environ,
        "HOME": "/home/openclaw",
        "GOG_ACCOUNT": GOG_ACCOUNT,
        "GOG_KEYRING_PASSWORD": os.environ.get("GOG_KEYRING_PASSWORD", ""),
    }


def _gog_update(tab, range_str, values_json):
    cmd = [GOG, "sheets", "update", SHEET_ID, range_str,
           "--values-json", values_json, "--input", "RAW",
           "--no-input", "--account", GOG_ACCOUNT]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_gog_env())
    if result.returncode != 0:
        log.error("gog update failed for %s: %s %s", tab, result.stdout, result.stderr)
        return False
    return True


def export_table(conn, table, tab_name, columns, since=None):
    """Export a table to a sheet tab."""
    where = f" WHERE date >= '{since}'" if since else ""
    rows = conn.execute(f"SELECT {', '.join(columns)} FROM {table}{where} ORDER BY date DESC").fetchall()
    if not rows:
        log.info("No rows to export for %s", tab_name)
        return 0

    # Build values array
    values = []
    for row in rows:
        values.append([str(row[c] if row[c] is not None else "") for c in range(len(columns))])

    # Write in batches of 50
    exported = 0
    for i in range(0, len(values), 50):
        batch = values[i:i+50]
        # Find existing rows by date and update, or append at bottom
        # For simplicity: clear and rewrite recent data
        start_row = 2 + i  # Skip header row
        end_row = start_row + len(batch) - 1
        end_col = chr(ord('A') + len(columns) - 1)
        range_str = f"{tab_name}!A{start_row}:{end_col}{end_row}"
        if _gog_update(tab_name, range_str, json.dumps(batch)):
            exported += len(batch)

    log.info("Exported %d rows to %s", exported, tab_name)
    return exported


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Export SQLite → Google Sheet")
    parser.add_argument("--full", action="store_true", help="Full export (not just recent)")
    args = parser.parse_args()

    if not SHEET_ID:
        log.error("SHEET_ID not set")
        sys.exit(1)

    conn = connect(DB_PATH)
    since = None if args.full else (date.today() - timedelta(days=7)).isoformat()

    tables = [
        ("body_metrics", "Body Metrics",
         ["date", "weight_lbs", "weight_kg", "body_fat_pct", "muscle_mass_kg",
          "water_pct", "bmi", "source", "notes"]),
        ("nutrition", "Nutrition",
         ["date", "calories", "protein_g", "carbs_g", "fat_g", "fiber_g",
          "sodium_mg", "source", "notes"]),
        ("recovery", "Recovery",
         ["date", "efficiency_pct", "sleep_hours", "steps", "active_minutes",
          "hrv", "resting_hr", "source", "notes", "sleep_score_computed", "time_in_bed_h"]),
        ("workout", "Training Log",
         ["date", "exercise", "sets", "reps", "weight_lbs", "rpe",
          "volume_lbs", "session_type", "source"]),
        ("cardio", "Cardio",
         ["date", "exercise", "duration_min", "speed", "incline",
          "net_calories", "met_used", "source", "notes"]),
    ]

    total = 0
    for table, tab, cols in tables:
        try:
            total += export_table(conn, table, tab, cols, since)
        except Exception as e:
            log.error("Failed to export %s: %s", table, e)

    conn.close()
    log.info("Export complete: %d total rows", total)


if __name__ == "__main__":
    main()
