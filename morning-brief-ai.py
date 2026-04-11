#!/usr/bin/env python3
"""J.A.R.V.I.S. AI Morning Brief — reads sheets, memory, and goals to generate
an intelligent daily brief. Replaces the static bash morning-brief.sh.

Runs via cron at 7am ET. Costs a few tokens (~$0.01) per run.
"""

import os
import sys
import json
import subprocess
import datetime
import pathlib
import urllib.request
import urllib.parse

# --- Config from env ---
SOUL_PATH = pathlib.Path("/home/openclaw/lifeos/soul.md")
MEMORY_DIR = pathlib.Path("/home/openclaw/lifeos/memory")
GOG = os.environ.get("GOG_PATH", "/usr/local/bin/gog")
GOG_ACCOUNT = os.environ["GOG_ACCOUNT"]
SHEET_ID = os.environ["SHEET_ID"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# AI config
AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get("XAI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.x.ai/v1")
AI_MODEL = os.environ.get("AI_MODEL", "grok-4-1-fast")


def gog_get(tab, rows=5):
    """Pull recent rows from a sheet tab, sorted by date (newest last)."""
    env = {**os.environ, "HOME": "/home/openclaw", "GOG_KEYRING_PASSWORD": os.environ.get("GOG_KEYRING_PASSWORD", "")}
    result = subprocess.run(
        [GOG, "sheets", "get", SHEET_ID, f"{tab}!A:Z", "--account", GOG_ACCOUNT, "--no-input"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    if result.returncode != 0:
        return f"(could not read {tab})"
    lines = result.stdout.strip().split("\n")
    header = lines[0] if lines else ""
    # Filter data rows, sort newest first (matches sheet order)
    data_lines = [l for l in lines[1:] if l.strip() and not l.startswith("←") and l[0:4].isdigit()]
    data_lines.sort(reverse=True)
    recent = data_lines[:rows]
    return header + "\n" + "\n".join(recent)


def load_memory():
    """Load the single memory.md file."""
    path = MEMORY_DIR / "memory.md"
    if not path.exists():
        return "No memories saved."
    return path.read_text().strip()


def count_pending_proposals():
    """Count pending soul proposals awaiting review."""
    proposals_path = pathlib.Path("/home/openclaw/lifeos/soul-proposals.jsonl")
    if not proposals_path.exists():
        return 0
    count = 0
    for line in proposals_path.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("status") in ("pending", "awaiting_user"):
                count += 1
        except json.JSONDecodeError:
            continue
    return count


def call_ai(prompt, system):
    """Call the AI API (OpenAI-compatible)."""
    from openai import OpenAI
    client = OpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)
    response = client.chat.completions.create(
        model=AI_MODEL,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


def send_telegram(text):
    """Send a message via Telegram Bot API. Raises on network failure."""
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "parse_mode": "Markdown",
        "text": text,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data=data,
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API rejected message: {result}")
        return True


def main():
    from zoneinfo import ZoneInfo
    now = datetime.datetime.now(ZoneInfo("America/Toronto"))

    # Gather data
    body_metrics = gog_get("Body Metrics", 7)
    training_log = gog_get("Training Log", 10)
    nutrition = gog_get("Nutrition", 7)
    recovery = gog_get("Recovery", 3)
    body_scans = gog_get("Body Scans", 2)
    memory = load_memory()
    pending_proposals = count_pending_proposals()
    soul = SOUL_PATH.read_text() if SOUL_PATH.exists() else ""

    system_prompt = soul + f"\n\nCurrent date/time: {now.strftime('%A, %Y-%m-%d %I:%M %p')} ET\n"

    user_prompt = f"""Generate the morning brief for today. Read the data below and give me:

1. What day it is and what workout is scheduled (or rest day)
2. Latest weight and trend (from Body Metrics)
3. Latest body fat from DEXA (from Body Scans — never use Renpho BF%)
4. Yesterday's nutrition summary and whether I hit protein target
5. Yesterday's recovery (sleep, steps)
6. Any goals or benchmarks from memory files to check progress against
7. One specific recommendation for today
8. A motivational line
9. Pending soul proposals: {pending_proposals} (if >0, remind me to review them — reply APPROVE or REJECT with the ID)

Be concise but human. This is read on a phone first thing in the morning.

--- BODY METRICS (recent) ---
{body_metrics}

--- TRAINING LOG (recent) ---
{training_log}

--- NUTRITION (recent) ---
{nutrition}

--- RECOVERY (recent) ---
{recovery}

--- BODY SCANS (DEXA) ---
{body_scans}

--- MEMORY FILES ---
{memory}

--- PENDING SOUL PROPOSALS ---
{pending_proposals} proposal(s) awaiting review
"""

    # Generate brief
    try:
        brief = call_ai(user_prompt, system_prompt)
    except Exception as e:
        # qa-check.sh Check 12 looks for "Morning brief sent" in last line of
        # this log. Anything else triggers the brief_not_sent alert.
        print(f"Morning brief FAILED: AI call errored: {e}", file=sys.stderr)
        sys.exit(1)

    if not brief:
        print("Morning brief FAILED: AI returned empty response", file=sys.stderr)
        sys.exit(1)

    # Send (Telegram has a 4096 char limit per message)
    try:
        for i in range(0, len(brief), 4096):
            send_telegram(brief[i:i+4096])
    except Exception as e:
        print(f"Morning brief FAILED: Telegram send errored: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Morning brief sent ({len(brief)} chars)")


if __name__ == "__main__":
    main()
