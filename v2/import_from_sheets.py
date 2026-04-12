#!/usr/bin/env python3
"""LifeOS v2 — One-shot importer from Google Sheets → lifeos.db

Reads every tab via the `gog` CLI, parses JSON rows, coerces types, and inserts
into a fresh SQLite database matching schema.sql. Fail-loud on any row that
won't fit the schema (no silent skips of required fields).

Usage (from inside v2/):
    . /opt/openclaw.env
    export GOG_KEYRING_PASSWORD GOG_ACCOUNT SHEET_ID
    python3 import_from_sheets.py
    python3 import_from_sheets.py --db /tmp/test.db   # custom path
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

V2_DIR = Path(__file__).resolve().parent
SCHEMA_SQL = V2_DIR / "schema.sql"
DEFAULT_DB = V2_DIR / "lifeos.db"

GOG_BIN = "/usr/local/bin/gog"

# Data rows must have a date in column A that matches YYYY-MM-DD.
# This rejects header rows, comment rows ("← One row per day…"), and empty rows.
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def iso_date(v: Any) -> str | None:
    """Return v as ISO-date string if it matches YYYY-MM-DD, else None."""
    s = v if isinstance(v, str) else (str(v) if v is not None else "")
    s = s.strip()
    return s if ISO_DATE_RE.match(s) else None


# ---------- gog fetch ----------

def gog_fetch(range_spec: str) -> list[list[Any]]:
    """Fetch a sheet range via gog. Returns list of rows (each a list of cells).
    Uses JSON + UNFORMATTED_VALUE so numbers come back as numbers, not display strings.
    """
    sheet_id = os.environ["SHEET_ID"]
    account = os.environ["GOG_ACCOUNT"]
    cmd = [
        GOG_BIN, "sheets", "get", sheet_id, range_spec,
        "--account", account, "--no-input",
        "-j", "--render", "UNFORMATTED_VALUE",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"gog failed for {range_spec!r}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    return data.get("values", [])


# ---------- type coercion helpers ----------

def to_real(v: Any) -> float | None:
    """Coerce cell to float or None. Empty strings → None."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def to_int(v: Any) -> int | None:
    r = to_real(v)
    if r is None:
        return None
    return int(round(r))


def to_text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def pad(row: list, n: int) -> list:
    """Pad with empty strings — gog omits trailing empty cells in JSON."""
    return row + [""] * (n - len(row))


# ---------- per-tab importers ----------
# Each returns (inserted_count, skipped_count). Skipped = rows with no date.

def import_body_metrics(cur: sqlite3.Cursor) -> tuple[int, int]:
    rows = gog_fetch("Body Metrics!A:I")
    data_rows = rows[1:] if rows else []
    inserted, skipped = 0, 0
    for r in data_rows:
        r = pad(r, 9)
        date = iso_date(r[0])
        if not date:
            skipped += 1
            continue
        cur.execute(
            "INSERT OR REPLACE INTO body_metrics "
            "(date, weight_lbs, weight_kg, body_fat_pct, muscle_mass_kg, water_pct, bmi, source, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (date, to_real(r[1]), to_real(r[2]), to_real(r[3]), to_real(r[4]),
             to_real(r[5]), to_real(r[6]), to_text(r[7]) or "UNKNOWN", to_text(r[8]))
        )
        inserted += 1
    return inserted, skipped


def import_body_scan(cur: sqlite3.Cursor) -> tuple[int, int]:
    # 16 columns: Date | Scan Type | BF% | Lean lbs | Lean kg | Bone Density |
    #             Visceral Fat | Trunk Fat% | Arms Fat% | Legs Fat% |
    #             Renpho Same Week | DEXA-Renpho Offset |
    #             Data Source | Source File | Notes | RMR (cal/day)
    rows = gog_fetch("Body Scans!A:P")
    data_rows = rows[1:] if rows else []
    inserted, skipped = 0, 0
    for r in data_rows:
        r = pad(r, 16)
        date = iso_date(r[0])
        if not date:
            skipped += 1
            continue
        cur.execute(
            "INSERT OR REPLACE INTO body_scan "
            "(date, scan_type, total_bf_pct, lean_mass_lbs, lean_mass_kg, bone_density, "
            " visceral_fat_area, trunk_fat_pct, arms_fat_pct, legs_fat_pct, renpho_bf_same_week, "
            " dexa_renpho_offset, rmr_cal, source, source_file, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (date, to_text(r[1]) or "UNKNOWN",
             to_real(r[2]), to_real(r[3]), to_real(r[4]),
             to_real(r[5]), to_real(r[6]), to_real(r[7]),
             to_real(r[8]), to_real(r[9]), to_real(r[10]), to_real(r[11]),
             to_real(r[15]),                       # RMR (col 16, index 15)
             to_text(r[12]) or "DEXA",             # Data Source
             to_text(r[13]),                       # Source File
             to_text(r[14]))                       # Notes
        )
        inserted += 1
    return inserted, skipped


def import_nutrition(cur: sqlite3.Cursor) -> tuple[int, int]:
    rows = gog_fetch("Nutrition!A:I")
    data_rows = rows[1:] if rows else []
    inserted, skipped = 0, 0
    for r in data_rows:
        r = pad(r, 9)
        date = iso_date(r[0])
        if not date:
            skipped += 1
            continue
        cur.execute(
            "INSERT OR REPLACE INTO nutrition "
            "(date, calories, protein_g, carbs_g, fat_g, fiber_g, sodium_mg, source, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (date, to_real(r[1]), to_real(r[2]), to_real(r[3]), to_real(r[4]),
             to_real(r[5]), to_real(r[6]), to_text(r[7]) or "UNKNOWN", to_text(r[8]))
        )
        inserted += 1
    return inserted, skipped


def import_workout(cur: sqlite3.Cursor) -> tuple[int, int]:
    rows = gog_fetch("Training Log!A:J")
    data_rows = rows[1:] if rows else []
    inserted, skipped = 0, 0
    for r in data_rows:
        r = pad(r, 10)
        date = iso_date(r[0])
        exercise = to_text(r[1])
        if not date or not exercise:
            skipped += 1
            continue
        sets = to_int(r[2])
        reps = to_int(r[3])
        weight = to_real(r[4])
        if sets is None or reps is None or weight is None:
            raise ValueError(
                f"Workout row missing required field (date={date}, "
                f"exercise={exercise}, sets={r[2]}, reps={r[3]}, weight={r[4]})"
            )
        cur.execute(
            "INSERT INTO workout "
            "(date, exercise, sets, reps, weight_lbs, rpe, volume_lbs, session_type, source, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (date, exercise, sets, reps, weight,
             to_real(r[5]),                        # RPE
             to_real(r[6]),                        # Volume
             to_text(r[7]),                        # Session Type
             to_text(r[8]) or "UNKNOWN",           # Data Source
             to_text(r[9]))                        # Notes
        )
        inserted += 1
    return inserted, skipped


def import_cardio(cur: sqlite3.Cursor) -> tuple[int, int]:
    rows = gog_fetch("Cardio!A:I")
    data_rows = rows[1:] if rows else []
    inserted, skipped = 0, 0
    for r in data_rows:
        r = pad(r, 9)
        date = iso_date(r[0])
        exercise = to_text(r[1])
        duration = to_real(r[2])
        if not date or not exercise or duration is None:
            skipped += 1
            continue
        cur.execute(
            "INSERT INTO cardio "
            "(date, exercise, duration_min, speed, incline, net_calories, met_used, source, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (date, exercise, duration, to_real(r[3]), to_real(r[4]),
             to_real(r[5]), to_real(r[6]), to_text(r[7]) or "UNKNOWN", to_text(r[8]))
        )
        inserted += 1
    return inserted, skipped


def import_recovery(cur: sqlite3.Cursor) -> tuple[int, int]:
    # 11 columns: Date | Efficiency% | Sleep Hours | Steps | Active Min | HRV |
    #             Resting HR | Data Source | Notes | Sleep Score (computed) | Time in Bed
    rows = gog_fetch("Recovery!A:K")
    data_rows = rows[1:] if rows else []
    inserted, skipped = 0, 0
    for r in data_rows:
        r = pad(r, 11)
        date = iso_date(r[0])
        if not date:
            skipped += 1
            continue
        cur.execute(
            "INSERT OR REPLACE INTO recovery "
            "(date, efficiency_pct, sleep_hours, steps, active_minutes, hrv, resting_hr, "
            " sleep_score_computed, time_in_bed_h, source, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (date,
             to_real(r[1]),                        # B Efficiency %
             to_real(r[2]),                        # C Sleep Hours
             to_int(r[3]),                         # D Steps
             to_int(r[4]),                         # E Active Minutes
             to_real(r[5]),                        # F HRV
             to_int(r[6]),                         # G Resting HR
             to_real(r[9]),                        # J Sleep Score (computed)
             to_real(r[10]),                       # K Time in Bed
             to_text(r[7]) or "UNKNOWN",           # H Data Source
             to_text(r[8]))                        # I Notes
        )
        inserted += 1
    return inserted, skipped


# ---------- main ----------

def create_db(db_path: Path) -> sqlite3.Connection:
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL.read_text())
    return conn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    for v in ("SHEET_ID", "GOG_ACCOUNT", "GOG_KEYRING_PASSWORD"):
        if v not in os.environ:
            print(f"FATAL: ${v} not set. Source /opt/openclaw.env first.", file=sys.stderr)
            sys.exit(2)

    db_path = Path(args.db)
    print(f"Creating fresh DB: {db_path}")
    conn = create_db(db_path)
    cur = conn.cursor()

    stages = [
        ("body_metrics", import_body_metrics),
        ("body_scan",    import_body_scan),
        ("nutrition",    import_nutrition),
        ("workout",      import_workout),
        ("cardio",       import_cardio),
        ("recovery",     import_recovery),
    ]

    print("\nImporting tabs...")
    totals = {}
    for name, fn in stages:
        inserted, skipped = fn(cur)
        totals[name] = inserted
        tag = f"  {name:<14}"
        skip_note = f" ({skipped} skipped)" if skipped else ""
        print(f"{tag} {inserted}{skip_note}")

    conn.commit()
    conn.close()

    total = sum(totals.values())
    print(f"\nImport complete. DB: {db_path}")
    print(f"Total rows inserted: {total}")
    print(f"DB size: {db_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
