#!/usr/bin/env python3
"""J.A.R.V.I.S. AI Morning Brief — reads sheets, memory, and goals to generate
an intelligent daily brief. Replaces the static bash morning-brief.sh.

Runs via cron at 7am ET. Costs a few tokens (~$0.01) per run.
"""

import os
import json
import subprocess
import datetime
import pathlib
import urllib.request

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
    """Pull recent rows from a sheet tab."""
    env = {**os.environ, "HOME": "/home/openclaw", "GOG_KEYRING_PASSWORD": os.environ.get("GOG_KEYRING_PASSWORD", "")}
    result = subprocess.run(
        [GOG, "sheets", "get", SHEET_ID, f"{tab}!A:Z", "--account", GOG_ACCOUNT, "--no-input"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    if result.returncode != 0:
        return f"(could not read {tab})"
    lines = result.stdout.strip().split("\n")
    header = lines[0] if lines else ""
    # Filter out empty rows
    data_lines = [l for l in lines[1:] if l.strip() and not l.startswith("←")]
    recent = data_lines[-rows:] if len(data_lines) > rows else data_lines
    return header + "\n" + "\n".join(recent)


def load_memory():
    """Load the single memory.md file."""
    path = MEMORY_DIR / "memory.md"
    if not path.exists():
        return "No memories saved."
    return path.read_text().strip()


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
    """Send a message via Telegram Bot API."""
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "parse_mode": "Markdown",
        "text": text,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data=data,
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        return result.get("ok", False)


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
"""

    # Generate brief
    brief = call_ai(user_prompt, system_prompt)

    # Send
    if brief:
        # Telegram has 4096 char limit
        for i in range(0, len(brief), 4096):
            send_telegram(brief[i:i+4096])
        print(f"Morning brief sent ({len(brief)} chars)")
    else:
        print("AI returned empty response")


if __name__ == "__main__":
    import urllib.parse
    main()
