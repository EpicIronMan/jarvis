#!/usr/bin/env python3
"""Fitbit -> SQLite sync for LifeOS v2.

Replaces v1 fitbit_sync.py. Key differences:
  - Writes to SQLite instead of Google Sheets
  - Preserves existing non-null values on partial updates (fixes the v1 overwrite bug)
  - Uses v2/handlers/log.py for writes (audit events included automatically)

Usage:
    python3 /home/openclaw/lifeos/v2/ingest_fitbit.py [--date YYYY-MM-DD]
"""

import argparse
import base64
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import urllib.error
import urllib.parse
import urllib.request

V2_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(V2_DIR))

from handlers.log import log_weight, log_nutrition, log_recovery
from handlers.query import connect

DB_PATH = V2_DIR / "lifeos.db"
ET = ZoneInfo("America/Toronto")

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
log = logging.getLogger("ingest_fitbit")


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


def compute_sleep_score(hours, efficiency, deep_min, rem_min):
    try:
        h = float(hours) if hours not in (None, "", 0) else 0
        e = float(efficiency) if efficiency not in (None, "") else 0
        d = float(deep_min) if deep_min not in (None, "") else 0
        r = float(rem_min) if rem_min not in (None, "") else 0
    except (ValueError, TypeError):
        return None
    if h == 0:
        return None
    duration_score = min(100, (h / 8) * 100)
    eff_score = e
    restoration_score = min(100, ((d + r) / 90) * 100)
    return round(0.5 * duration_score + 0.25 * eff_score + 0.25 * restoration_score)


def pull_body_metrics(conn, tokens, cfg, dt):
    ds = dt.strftime("%Y-%m-%d")
    log.info("Pulling body metrics for %s", ds)
    data = fitbit_get(f"/1/user/-/body/log/weight/date/{ds}.json", tokens, cfg)
    weights = data.get("weight", [])
    if not weights:
        log.info("No weight data for %s", ds)
        return
    entry = weights[-1]
    weight_kg = entry.get("weight")
    bf = entry.get("fat")
    if not weight_kg:
        return
    weight_lbs = round(weight_kg * 2.20462, 1)
    synced_at = datetime.now(ET).strftime("%H:%M ET")
    result = log_weight(conn, weight_lbs, body_fat_pct=bf, source="FITBIT",
                        notes=f"synced {synced_at}", date_str=ds)
    log.info("Body metrics written: %s", result)


def pull_sleep(tokens, cfg, dt):
    ds = dt.strftime("%Y-%m-%d")
    log.info("Pulling sleep data for %s", ds)
    data = fitbit_get(f"/1.2/user/-/sleep/date/{ds}.json", tokens, cfg)
    sleeps = data.get("sleep", [])
    if not sleeps:
        log.info("No sleep data for %s", ds)
        return None

    total_minutes_asleep = sum(s.get("minutesAsleep", 0) for s in sleeps)
    total_time_in_bed = sum(s.get("timeInBed", 0) for s in sleeps)
    total_deep_min = total_rem_min = 0
    for s in sleeps:
        summary = s.get("levels", {}).get("summary", {})
        total_deep_min += summary.get("deep", {}).get("minutes", 0)
        total_rem_min += summary.get("rem", {}).get("minutes", 0)

    hours = round(total_minutes_asleep / 60, 1) if total_minutes_asleep else None
    time_in_bed_h = round(total_time_in_bed / 60, 1) if total_time_in_bed else None

    if total_minutes_asleep > 0:
        weighted_eff = sum(
            s.get("efficiency", 0) * s.get("minutesAsleep", 0) for s in sleeps
        ) / total_minutes_asleep
        efficiency = round(weighted_eff)
    else:
        efficiency = None

    computed_score = compute_sleep_score(hours, efficiency, total_deep_min, total_rem_min)

    return {
        "efficiency": efficiency,
        "hours": hours,
        "time_in_bed_h": time_in_bed_h,
        "computed_score": computed_score,
    }


def pull_activity(tokens, cfg, dt):
    ds = dt.strftime("%Y-%m-%d")
    log.info("Pulling activity data for %s", ds)
    data = fitbit_get(f"/1/user/-/activities/date/{ds}.json", tokens, cfg)
    summary = data.get("summary", {})
    steps = summary.get("steps") or None
    active_mins = (summary.get("fairlyActiveMinutes", 0) + summary.get("veryActiveMinutes", 0)) or None

    resting_hr = None
    try:
        hr_data = fitbit_get(f"/1/user/-/activities/heart/date/{ds}/1d.json", tokens, cfg)
        hr_zones = hr_data.get("activities-heart", [])
        if hr_zones:
            resting_hr = hr_zones[0].get("value", {}).get("restingHeartRate")
    except Exception as e:
        log.warning("Could not fetch HR data: %s", e)

    return {"steps": steps, "active_mins": active_mins, "resting_hr": resting_hr}


def pull_nutrition_data(conn, tokens, cfg, dt):
    ds = dt.strftime("%Y-%m-%d")
    log.info("Pulling nutrition data for %s", ds)
    data = fitbit_get(f"/1/user/-/foods/log/date/{ds}.json", tokens, cfg)
    summary = data.get("summary", {})
    calories = summary.get("calories")
    if not calories:
        log.info("No nutrition data for %s", ds)
        return

    synced_at = datetime.now(ET).strftime("%H:%M ET")
    result = log_nutrition(
        conn, calories=float(calories),
        protein_g=float(summary.get("protein", 0)),
        carbs_g=float(summary.get("carbs", 0)) or None,
        fat_g=float(summary.get("fat", 0)) or None,
        fiber_g=float(summary.get("fiber", 0)) or None,
        sodium_mg=float(summary.get("sodium", 0)) or None,
        source="FITBIT", notes=f"synced {synced_at}", date_str=ds,
    )
    log.info("Nutrition written: %s", result)


def main():
    parser = argparse.ArgumentParser(description="Fitbit -> SQLite sync (v2)")
    parser.add_argument("--date", help="Date to sync (YYYY-MM-DD), default today")
    args = parser.parse_args()

    dt = date.fromisoformat(args.date) if args.date else date.today()

    if not os.path.exists(TOKEN_PATH):
        log.error("No tokens found. Run fitbit_auth.py first.")
        sys.exit(1)

    cfg = load_config()
    tokens = load_tokens()
    conn = connect(DB_PATH)

    log.info("=== Fitbit sync (v2/SQLite) starting for %s ===", dt)

    try:
        pull_body_metrics(conn, tokens, cfg, dt)
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
            ds = dt.strftime("%Y-%m-%d")
            synced_at = datetime.now(ET).strftime("%H:%M ET")
            result = log_recovery(
                conn, date_str=ds,
                efficiency_pct=sleep_data.get("efficiency") if sleep_data else None,
                sleep_hours=sleep_data.get("hours") if sleep_data else None,
                time_in_bed_h=sleep_data.get("time_in_bed_h") if sleep_data else None,
                sleep_score_computed=sleep_data.get("computed_score") if sleep_data else None,
                steps=activity_data.get("steps") if activity_data else None,
                active_minutes=activity_data.get("active_mins") if activity_data else None,
                resting_hr=activity_data.get("resting_hr") if activity_data else None,
                source="FITBIT", notes=f"synced {synced_at}",
            )
            log.info("Recovery written: %s", result)
        except Exception as e:
            log.error("Recovery write failed: %s", e)

    try:
        pull_nutrition_data(conn, tokens, cfg, dt)
    except Exception as e:
        log.error("Nutrition pull failed: %s", e)

    conn.close()
    log.info("=== Fitbit sync (v2/SQLite) complete ===")


if __name__ == "__main__":
    main()
