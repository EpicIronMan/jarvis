#!/usr/bin/env python3
"""Deterministic morning brief for LifeOS v2.

Reads from SQLite (not Sheets), assembles structured context, calls LLM
for prose synthesis, sends to Telegram. The LLM only writes coaching
prose — all data assembly is deterministic.

Usage:
    python3 /home/openclaw/lifeos/v2/morning_brief.py
"""

import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import urllib.request
import urllib.parse

V2_DIR = Path(__file__).resolve().parent
LIFEOS_DIR = V2_DIR.parent
sys.path.insert(0, str(V2_DIR))

from handlers.query import (
    connect, latest_weight, latest_body_scan, nutrition_for_date,
    recovery_for_date, last_training_session, weight_range,
    nutrition_range_summary, stats_snapshot,
)
from handlers.dates import today, yesterday, days_ago, today_et

DB_PATH = V2_DIR / "lifeos.db"
ET = ZoneInfo("America/Toronto")

LOG_PATH = LIFEOS_DIR / "morning-brief.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("morning_brief")


def _send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("CHAT_ID", "")
    if not token or not chat_id:
        log.error("TELEGRAM_BOT_TOKEN or CHAT_ID not set")
        return
    # Send in chunks if needed
    for i in range(0, len(text), 4096):
        chunk = text[i:i+4096]
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": chunk}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            log.error("Telegram send failed: %s", e)


def _build_context(conn) -> dict:
    """Assemble all data the brief needs — deterministically from SQLite."""
    today_str = today()
    yesterday_str = yesterday()
    today_d = today_et()
    day_name = today_d.strftime("%A")

    # Weight trend (last 7 days)
    start_7d = (today_d - timedelta(days=6)).isoformat()
    wt = weight_range(conn, start_7d, today_str)

    # Yesterday's nutrition
    nut = nutrition_for_date(conn, yesterday_str)

    # Yesterday's recovery
    rec = recovery_for_date(conn, yesterday_str)

    # Latest body scan (DEXA)
    scan = latest_body_scan(conn)

    # Last training
    training = last_training_session(conn)

    # Nutrition average (last 7 days)
    nut_avg = nutrition_range_summary(conn, start_7d, today_str)

    # User facts (protein target, goals)
    facts = {}
    for row in conn.execute("SELECT key, value FROM user_facts").fetchall():
        facts[row[0]] = row[1]

    # Pending soul proposals
    proposals_path = LIFEOS_DIR / "soul-proposals.jsonl"
    pending_proposals = 0
    if proposals_path.exists():
        for line in proposals_path.read_text().strip().split("\n"):
            if line:
                try:
                    p = json.loads(line)
                    if p.get("status") == "pending":
                        pending_proposals += 1
                except json.JSONDecodeError:
                    pass

    return {
        "day_name": day_name,
        "date": today_str,
        "latest_weight": latest_weight(conn),
        "weight_trend_7d": {
            "n": wt["n"],
            "start": wt.get("start_weight"),
            "end": wt.get("end_weight"),
            "change": wt.get("change"),
        },
        "yesterday_nutrition": nut,
        "nutrition_avg_7d": {
            "avg_calories": nut_avg.get("avg_calories"),
            "avg_protein_g": nut_avg.get("avg_protein_g"),
            "n_days": nut_avg.get("n_with_calories", 0),
        },
        "yesterday_recovery": rec,
        "latest_dexa": {
            "date": scan["date"] if scan else None,
            "total_bf_pct": scan["total_bf_pct"] if scan else None,
            "lean_mass_lbs": scan.get("lean_mass_lbs") if scan else None,
            "rmr_cal": scan.get("rmr_cal") if scan else None,
        } if scan else None,
        "last_training": {
            "date": training["date"],
            "exercises": [e["exercise"] for e in training.get("exercises", [])],
        },
        "user_facts": facts,
        "pending_proposals": pending_proposals,
    }


def _generate_brief(context: dict) -> str:
    """Call LLM for coaching prose based on assembled data."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # Fall back to building a template-based brief
        return _template_brief(context)

    client = anthropic.Anthropic(api_key=api_key)

    system = (
        "You are a personal fitness coach writing a concise daily morning brief. "
        "Use the structured data provided. Be direct, specific, and motivational. "
        "Include: today's day/date, weight + trend, yesterday's nutrition + protein hit, "
        "yesterday's sleep/recovery, body composition from latest DEXA (NOT Renpho), "
        "last workout, and one specific recommendation for today. "
        "Keep it under 300 words. No markdown headers — use plain text with line breaks."
    )

    if context.get("pending_proposals", 0) > 0:
        system += f"\n\nMention that there are {context['pending_proposals']} pending soul proposals awaiting review."

    resp = client.messages.create(
        model="claude-sonnet-4-5-20241022",
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": json.dumps(context, default=str)}],
    )
    return resp.content[0].text


def _template_brief(ctx: dict) -> str:
    """Fallback template brief when LLM is unavailable."""
    lines = [f"Good morning! {ctx['day_name']}, {ctx['date']}"]

    w = ctx.get("latest_weight")
    if w:
        trend = ctx.get("weight_trend_7d", {})
        change = trend.get("change")
        trend_str = f" ({change:+.1f} lbs / 7d)" if change is not None else ""
        lines.append(f"\nWeight: {w['weight_lbs']} lbs{trend_str}")

    dexa = ctx.get("latest_dexa")
    if dexa and dexa.get("total_bf_pct"):
        lines.append(f"Body fat (DEXA {dexa['date']}): {dexa['total_bf_pct']}%")

    nut = ctx.get("yesterday_nutrition")
    if nut:
        lines.append(f"\nYesterday's nutrition: {nut.get('calories', '?')} cal, {nut.get('protein_g', '?')}g protein")

    rec = ctx.get("yesterday_recovery")
    if rec:
        parts = []
        if rec.get("sleep_hours"):
            parts.append(f"{rec['sleep_hours']}h sleep")
        if rec.get("steps"):
            parts.append(f"{rec['steps']:,} steps")
        if parts:
            lines.append(f"Recovery: {', '.join(parts)}")

    t = ctx.get("last_training")
    if t and t.get("date"):
        lines.append(f"\nLast workout ({t['date']}): {', '.join(t.get('exercises', [])[:5])}")

    if ctx.get("pending_proposals", 0) > 0:
        lines.append(f"\n{ctx['pending_proposals']} soul proposal(s) pending review.")

    return "\n".join(lines)


def main():
    conn = connect(DB_PATH)
    try:
        context = _build_context(conn)
        brief = _generate_brief(context)
        _send_telegram(brief)
        log.info("Morning brief sent")
    except Exception as e:
        log.error("Morning brief failed: %s", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
