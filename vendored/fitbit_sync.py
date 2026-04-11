#!/usr/bin/env python3
"""Fitbit -> Google Sheets sync script.

Pulls today's data from Fitbit API and writes to fitness_master_log
via gog sheets append. Handles token refresh automatically.

Usage:
    python3 /home/openclaw/fitbit_sync.py [--date YYYY-MM-DD]
"""

import argparse
import base64
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

CONFIG_PATH = os.path.expanduser("~/.config/fitbit/fitbit_config.json")
TOKEN_PATH = os.path.expanduser("~/.config/fitbit/tokens.json")
LOG_PATH = os.path.expanduser("~/.config/fitbit/sync.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("fitbit_sync")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_tokens():
    with open(TOKEN_PATH) as f:
        return json.load(f)


def save_tokens(data):
    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(TOKEN_PATH, 0o600)


def refresh_access_token(cfg, tokens):
    """Refresh the Fitbit access token using the refresh token."""
    log.info("Refreshing access token...")
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": client_id,
    }).encode()
    req = urllib.request.Request(
        "https://api.fitbit.com/oauth2/token",
        data=data,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    with urllib.request.urlopen(req) as resp:
        new_tokens = json.loads(resp.read())

    save_tokens(new_tokens)
    log.info("Token refreshed successfully.")
    return new_tokens


def fitbit_get(endpoint, tokens, cfg):
    """Make a GET request to the Fitbit API. Auto-refreshes on 401."""
    url = f"https://api.fitbit.com{endpoint}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "application/json",
    })

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            tokens = refresh_access_token(cfg, tokens)
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        else:
            body = e.read().decode()
            log.error("Fitbit API error %d: %s — %s", e.code, endpoint, body)
            raise


def _gog_env(cfg):
    env = os.environ.copy()
    env["GOG_ACCOUNT"] = cfg["gog_account"]
    env["GOG_KEYRING_PASSWORD"] = os.environ.get("GOG_KEYRING_PASSWORD", "")
    return env


def _find_row_for_date(cfg, tab, ds):
    """Find the row number for a given date in a sheet tab. Returns None if not found."""
    sheet_id = cfg["sheet_id"]
    gog = cfg["gog_bin"]
    account = cfg["gog_account"]
    env = _gog_env(cfg)

    cmd = [gog, "sheets", "get", sheet_id, f"{tab}!A:A", "--account", account, "--no-input"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    if result.returncode != 0:
        return None

    for i, line in enumerate(result.stdout.strip().split("\n"), start=1):
        if line.strip().startswith(ds):
            return i
    return None


def _find_first_data_row(cfg, tab):
    """Find the first row that contains date data (skip header/comments). Returns row number."""
    sheet_id = cfg["sheet_id"]
    gog = cfg["gog_bin"]
    account = cfg["gog_account"]
    env = _gog_env(cfg)

    cmd = [gog, "sheets", "get", sheet_id, f"{tab}!A:A", "--account", account, "--no-input"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    if result.returncode != 0:
        return 3  # default: after header + comment row

    for i, line in enumerate(result.stdout.strip().split("\n"), start=1):
        if line.strip() and len(line.strip()) >= 4 and line.strip()[0:4].isdigit():
            return i
    return 3


def gog_sheets_upsert(cfg, tab, ds, values_json, end_col="I"):
    """Insert or update a row for the given date. New rows insert at top (newest first).

    end_col is the rightmost column the row writes to. Recovery uses 'J' (extra
    Sleep Score column added 2026-04-11); other tabs use 'I'.
    """
    sheet_id = cfg["sheet_id"]
    gog = cfg["gog_bin"]
    account = cfg["gog_account"]
    env = _gog_env(cfg)

    existing_row = _find_row_for_date(cfg, tab, ds)

    if existing_row:
        # Update existing row in place
        range_spec = f"{tab}!A{existing_row}:{end_col}{existing_row}"
        cmd = [
            gog, "sheets", "update", sheet_id, range_spec,
            "--values-json", values_json,
            "--input", "RAW",
            "--no-input",
            "--account", account,
        ]
        log.info("gog update %s row %d: %s", tab, existing_row, values_json)
    else:
        # Insert new row at top of data (newest first)
        first_data = _find_first_data_row(cfg, tab)
        range_spec = f"{tab}!A{first_data}:{end_col}{first_data}"
        cmd = [
            gog, "sheets", "append", sheet_id, range_spec,
            "--values-json", values_json,
            "--insert", "OVERWRITE",
            "--input", "RAW",
            "--no-input",
            "--account", account,
        ]
        log.info("gog insert at top %s (row %d): %s", tab, first_data, values_json)

    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    if result.returncode != 0:
        log.error("gog upsert failed: %s %s", result.stdout, result.stderr)
        return False
    log.info("gog upsert ok: %s", result.stdout.strip())
    return True


def pull_body_metrics(tokens, cfg, dt):
    """Pull weight and body fat from Fitbit for the given date."""
    ds = dt.strftime("%Y-%m-%d")
    log.info("Pulling body metrics for %s", ds)

    data = fitbit_get(f"/1/user/-/body/log/weight/date/{ds}.json", tokens, cfg)
    weights = data.get("weight", [])
    if not weights:
        log.info("No weight data for %s", ds)
        return

    # Use the last entry of the day (most recent)
    entry = weights[-1]
    weight_kg = entry.get("weight", "")
    bmi = entry.get("bmi", "")
    fat = entry.get("fat", "")

    # Convert kg to lbs
    weight_lbs = round(weight_kg * 2.20462, 1) if weight_kg else ""
    weight_kg = round(weight_kg, 1) if weight_kg else ""

    synced_at = datetime.now(tz=__import__('zoneinfo').ZoneInfo("America/Toronto")).strftime("%H:%M ET")
    row = json.dumps([[
        ds,
        str(weight_lbs),   # Weight (lbs)
        str(weight_kg),     # Weight (kg)
        str(fat),           # Body Fat %
        "",                 # Muscle Mass (kg) — not in Fitbit
        "",                 # Water % — not in Fitbit
        str(bmi),           # BMI
        "FITBIT",           # Data Source
        f"synced {synced_at}",  # Notes
    ]])

    gog_sheets_upsert(cfg, "Body Metrics", ds, row)


def compute_sleep_score(hours, efficiency, deep_min, rem_min):
    """Approximate Fitbit-style sleep score (0-100). Returns string for sheet cell.

    Fitbit's actual Sleep Score is NOT exposed in the public Web API — only the mobile
    app has it. This is a proxy that produces comparable rankings: 50% duration weight
    (target 8h), 25% efficiency, 25% restoration (deep+REM, target 90 min). Won't exactly
    match the app's number but should rank nights similarly.
    """
    try:
        h = float(hours) if hours not in (None, "") else 0
        e = float(efficiency) if efficiency not in (None, "") else 0
        d = float(deep_min) if deep_min not in (None, "") else 0
        r = float(rem_min) if rem_min not in (None, "") else 0
    except (ValueError, TypeError):
        return ""
    if h == 0:
        return ""
    duration_score = min(100, (h / 8) * 100)
    eff_score = e
    restoration_score = min(100, ((d + r) / 90) * 100)
    score = 0.5 * duration_score + 0.25 * eff_score + 0.25 * restoration_score
    return str(round(score))


def pull_sleep(tokens, cfg, dt):
    """Pull sleep data from Fitbit for the given date.

    Sums across ALL sleep sessions (main + naps), not just the main overnight session.
    Previously this only counted `isMainSleep`, so a 30-min nap on top of a 7h night
    showed as 7.0 hours instead of 7.5. Fixed 2026-04-11.
    """
    ds = dt.strftime("%Y-%m-%d")
    log.info("Pulling sleep data for %s", ds)

    data = fitbit_get(f"/1.2/user/-/sleep/date/{ds}.json", tokens, cfg)
    sleeps = data.get("sleep", [])
    if not sleeps:
        log.info("No sleep data for %s", ds)
        return

    # Sum across ALL sleep sessions (main + naps)
    total_minutes_asleep = sum(s.get("minutesAsleep", 0) for s in sleeps)
    total_time_in_bed = sum(s.get("timeInBed", 0) for s in sleeps)
    total_deep_min = 0
    total_light_min = 0
    total_rem_min = 0
    total_wake_min = 0
    for s in sleeps:
        summary = s.get("levels", {}).get("summary", {})
        total_deep_min  += summary.get("deep",  {}).get("minutes", 0)
        total_light_min += summary.get("light", {}).get("minutes", 0)
        total_rem_min   += summary.get("rem",   {}).get("minutes", 0)
        total_wake_min  += summary.get("wake",  {}).get("minutes", 0)

    hours = round(total_minutes_asleep / 60, 1) if total_minutes_asleep else 0
    time_in_bed_h = round(total_time_in_bed / 60, 1) if total_time_in_bed else 0

    # Efficiency: weighted by minutesAsleep across all sessions, falls back to main's efficiency.
    # If user only had a main session, this just equals the main efficiency.
    if total_minutes_asleep > 0:
        weighted_eff = sum(
            s.get("efficiency", 0) * s.get("minutesAsleep", 0) for s in sleeps
        ) / total_minutes_asleep
        efficiency = round(weighted_eff)
    else:
        efficiency = ""

    # Stages summary string for the Notes column
    stage_info = []
    for label, mins in (("deep", total_deep_min), ("light", total_light_min),
                        ("rem", total_rem_min), ("wake", total_wake_min)):
        if mins:
            stage_info.append(f"{label}:{mins}m")
    if len(sleeps) > 1:
        stage_info.append(f"sessions:{len(sleeps)}")
    stage_str = " ".join(stage_info)

    # Note: Fitbit's real Sleep Score isn't in the public API. We compute a proxy.
    # The "efficiency" field is the % of time-in-bed actually asleep — useful but
    # NOT the same as the app's Sleep Score. We store both, in different columns.
    computed_score = compute_sleep_score(hours, efficiency, total_deep_min, total_rem_min)

    return {
        "date": ds,
        "efficiency": str(efficiency),         # % of time in bed asleep (weighted across sessions)
        "computed_score": computed_score,      # 0-100 proxy of Fitbit's app Sleep Score
        "hours": str(hours),                   # TOTAL hours asleep across all sessions
        "time_in_bed_h": str(time_in_bed_h),   # TOTAL hours in bed (raw) — includes wake time within sessions
        "stages": stage_str,
    }


def pull_activity(tokens, cfg, dt):
    """Pull steps, active minutes, resting HR from Fitbit."""
    ds = dt.strftime("%Y-%m-%d")
    log.info("Pulling activity data for %s", ds)

    data = fitbit_get(f"/1/user/-/activities/date/{ds}.json", tokens, cfg)
    summary = data.get("summary", {})
    steps = summary.get("steps", "")
    active_mins = (
        summary.get("fairlyActiveMinutes", 0)
        + summary.get("veryActiveMinutes", 0)
    )

    resting_hr = ""
    try:
        hr_data = fitbit_get(f"/1/user/-/activities/heart/date/{ds}/1d.json", tokens, cfg)
        hr_zones = hr_data.get("activities-heart", [])
        if hr_zones:
            resting_hr = hr_zones[0].get("value", {}).get("restingHeartRate", "")
    except Exception as e:
        log.warning("Could not fetch HR data: %s", e)

    return {
        "date": ds,
        "steps": str(steps),
        "active_mins": str(active_mins),
        "resting_hr": str(resting_hr),
    }


def write_recovery(cfg, sleep_data, activity_data, dt):
    """Combine sleep + activity into one Recovery row.

    Schema (11 columns A:K after 2026-04-11 sleep score fix + time-in-bed addition):
      A Date | B Efficiency % | C Sleep Hours | D Steps | E Active Minutes
      F HRV  | G Resting HR  | H Data Source | I Notes | J Sleep Score (computed)
      K Time in Bed (h)

    - Column B "Efficiency %" was previously misnamed "Sleep Score" but always held
      efficiency (Fitbit Web API doesn't expose the real Sleep Score).
    - Column C "Sleep Hours" = actual time asleep (sum of minutesAsleep across all
      sleep sessions including naps).
    - Column J "Sleep Score (computed)" is our 0-100 proxy. See compute_sleep_score().
    - Column K "Time in Bed (h)" = raw period in bed (sum of timeInBed across all
      sessions). Includes wake time within sessions. K - C = restless minutes.
    """
    ds = dt.strftime("%Y-%m-%d")

    efficiency_pct = sleep_data.get("efficiency", "") if sleep_data else ""
    computed_score = sleep_data.get("computed_score", "") if sleep_data else ""
    sleep_hours = sleep_data.get("hours", "") if sleep_data else ""
    time_in_bed = sleep_data.get("time_in_bed_h", "") if sleep_data else ""
    stages = sleep_data.get("stages", "") if sleep_data else ""
    steps = activity_data.get("steps", "") if activity_data else ""
    active_mins = activity_data.get("active_mins", "") if activity_data else ""
    resting_hr = activity_data.get("resting_hr", "") if activity_data else ""

    synced_at = datetime.now(tz=__import__('zoneinfo').ZoneInfo("America/Toronto")).strftime("%H:%M ET")
    notes = f"{stages} synced {synced_at}" if stages else f"synced {synced_at}"

    row = json.dumps([[
        ds,
        efficiency_pct, # B Efficiency % (raw Fitbit metric, % time in bed asleep)
        sleep_hours,    # C Sleep Hours (actual asleep, all sessions summed)
        steps,          # D Steps
        active_mins,    # E Active Minutes
        "",             # F HRV — not in standard Fitbit API
        resting_hr,     # G Resting HR
        "FITBIT",       # H Data Source
        notes,          # I Notes (sleep stages + sync timestamp)
        computed_score, # J Sleep Score (computed proxy of Fitbit app score)
        time_in_bed,    # K Time in Bed (h) — raw, includes wake time within sessions
    ]])

    gog_sheets_upsert(cfg, "Recovery", ds, row, end_col="K")


def pull_nutrition(tokens, cfg, dt):
    """Pull food/nutrition log from Fitbit (synced from MyFitnessPal)."""
    ds = dt.strftime("%Y-%m-%d")
    log.info("Pulling nutrition data for %s", ds)

    data = fitbit_get(f"/1/user/-/foods/log/date/{ds}.json", tokens, cfg)
    summary = data.get("summary", {})
    calories = summary.get("calories", "")
    protein = summary.get("protein", "")
    carbs = summary.get("carbs", "")
    fat = summary.get("fat", "")
    fiber = summary.get("fiber", "")
    sodium = summary.get("sodium", "")

    if not calories:
        log.info("No nutrition data for %s", ds)
        return

    synced_at = datetime.now(tz=__import__('zoneinfo').ZoneInfo("America/Toronto")).strftime("%H:%M ET")
    row = json.dumps([[
        ds,
        str(calories),  # Calories
        str(protein),   # Protein (g)
        str(carbs),     # Carbs (g)
        str(fat),       # Fat (g)
        str(fiber),     # Fiber (g)
        str(sodium),    # Sodium (mg)
        "FITBIT",       # Data Source
        f"synced {synced_at}",  # Notes
    ]])

    gog_sheets_upsert(cfg, "Nutrition", ds, row)


def main():
    parser = argparse.ArgumentParser(description="Fitbit -> Google Sheets sync")
    parser.add_argument("--date", help="Date to sync (YYYY-MM-DD), default today")
    args = parser.parse_args()

    dt = date.fromisoformat(args.date) if args.date else date.today()

    if not os.path.exists(TOKEN_PATH):
        log.error("No tokens found. Run fitbit_auth.py first.")
        sys.exit(1)

    cfg = load_config()
    tokens = load_tokens()

    log.info("=== Fitbit sync starting for %s ===", dt)

    try:
        pull_body_metrics(tokens, cfg, dt)
    except Exception as e:
        log.error("Body metrics pull failed: %s", e)

    sleep_data = None
    try:
        sleep_data = pull_sleep(tokens, cfg, dt)
    except Exception as e:
        log.error("Sleep pull failed: %s", e)

    activity_data = None
    try:
        activity_data = pull_activity(tokens, cfg, dt)
    except Exception as e:
        log.error("Activity pull failed: %s", e)

    if sleep_data or activity_data:
        try:
            write_recovery(cfg, sleep_data, activity_data, dt)
        except Exception as e:
            log.error("Recovery write failed: %s", e)

    try:
        pull_nutrition(tokens, cfg, dt)
    except Exception as e:
        log.error("Nutrition pull failed: %s", e)

    log.info("=== Fitbit sync complete ===")


if __name__ == "__main__":
    main()
