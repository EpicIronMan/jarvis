#!/usr/bin/env python3
"""Proactive coaching triggers for LifeOS v2.

Checks SQLite for concerning patterns and sends Telegram alerts.
Runs daily after QA check (e.g. 9am ET via cron).

Triggers:
  1. no-training-2d: No workout logged in 2+ days
  2. protein-below-target-3d: Average protein below target for 3+ days
  3. weight-wrong-direction-7d: Weight trending up when goal is to lose (or vice versa)
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

V2_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(V2_DIR))

from handlers.query import connect, weight_range, nutrition_range_summary
from handlers.dates import today_et

DB_PATH = V2_DIR / "lifeos.db"
LOG_PATH = V2_DIR / "triggers.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("triggers")


def _send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("CHAT_ID", "")
    if not token or not chat_id:
        return
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        log.error("Telegram send failed: %s", e)


def check_no_training(conn, today_d) -> str | None:
    """Alert if no workout in 2+ days."""
    two_days_ago = (today_d - timedelta(days=2)).isoformat()
    row = conn.execute(
        "SELECT MAX(date) as last_date FROM workout"
    ).fetchone()
    if not row or not row[0]:
        return None
    last_date = row[0]
    if last_date < two_days_ago:
        days_since = (today_d - date.fromisoformat(last_date)).days
        return f"No training logged in {days_since} days (last: {last_date}). Rest day or missed log?"
    return None


def check_protein_below_target(conn, today_d) -> str | None:
    """Alert if avg protein below target for 3+ days."""
    # Get protein target from lean mass * 1.2g
    scan = conn.execute("SELECT lean_mass_lbs FROM body_scan ORDER BY date DESC LIMIT 1").fetchone()
    if not scan or not scan[0]:
        return None
    lean_mass = float(scan[0])
    target_protein = lean_mass * 1.2  # low end of 1.2-1.4g/lb

    three_days_ago = (today_d - timedelta(days=2)).isoformat()
    summary = nutrition_range_summary(conn, three_days_ago, today_d.isoformat())
    if summary.get("n_with_protein", 0) < 2:
        return None  # Not enough data
    avg = summary.get("avg_protein_g")
    if avg and avg < target_protein * 0.7:  # Below 70% of target
        return (
            f"Protein averaging {avg:.0f}g/day over last {summary['n_with_protein']} days "
            f"(target: {target_protein:.0f}g from {lean_mass:.0f} lbs lean mass)."
        )
    return None


def check_weight_direction(conn, today_d) -> str | None:
    """Alert if weight trending wrong direction over 7 days."""
    row = conn.execute("SELECT value FROM user_facts WHERE key = 'goal_weight_lbs'").fetchone()
    if not row:
        return None
    goal_weight = float(row[0])

    seven_days_ago = (today_d - timedelta(days=6)).isoformat()
    wt = weight_range(conn, seven_days_ago, today_d.isoformat())
    if wt["n"] < 4:
        return None  # Not enough data

    change = wt.get("change")
    if change is None:
        return None

    current = wt.get("end_weight")
    if current is None:
        return None

    # If goal is below current (losing), weight should be going down
    if goal_weight < current and change > 1.0:
        return (
            f"Weight up {change:+.1f} lbs this week ({wt['start_weight']} → {wt['end_weight']}) "
            f"while goal is {goal_weight} lbs. Review nutrition?"
        )
    # If goal is above current (gaining), weight should be going up
    if goal_weight > current and change < -1.0:
        return (
            f"Weight down {change:+.1f} lbs this week while goal is {goal_weight} lbs. "
            f"Eating enough?"
        )
    return None


def main():
    conn = connect(DB_PATH)
    today_d = today_et()
    alerts = []

    for check in [check_no_training, check_protein_below_target, check_weight_direction]:
        try:
            msg = check(conn, today_d)
            if msg:
                alerts.append(msg)
                log.info("Trigger fired: %s", msg)
        except Exception as e:
            log.error("Trigger check failed: %s", e)

    conn.close()

    if alerts:
        text = "Coaching triggers:\n\n" + "\n\n".join(f"- {a}" for a in alerts)
        _send_telegram(text)
        log.info("Sent %d trigger alert(s)", len(alerts))
    else:
        log.info("No triggers fired")


if __name__ == "__main__":
    main()
