# J.A.R.V.I.S. — Architecture Document

Last updated: 2026-04-05

## Maintenance Rule

**Any AI or human that changes any file in this repo MUST update this file in the same session.** If the "Last updated" date is old, verify against the actual files before trusting this doc.

## What This Is

J.A.R.V.I.S. (Just A Rather Very Intelligent System) — a personal fitness coaching and life-tracking system accessible via Telegram. An AI (Grok 4.1 Fast via xAI) receives messages, interprets them, logs data to Google Sheets, and replies with coaching/analysis.

## Why It Exists

the user is on an aggressive cut (1000 cal/day deficit) from ~26% body fat targeting 10-12%. He needs:
- Quick workout logging from his phone (Telegram shorthand like "bench 275x5x3")
- Daily weight/nutrition tracking
- AI coaching that's data-driven and direct
- All data stored durably so any AI tool can pick up where the last left off

## System Overview

```
the user's Phone (Telegram)
       |
       v
Telegram Bot API (polling)
       |
       v
+--------------------------------------+
|  /home/openclaw/lifeos/bot.py        |  <-- Single Python file (~400 lines)
|  Grok 4.1 Fast via xAI (OpenAI SDK) |
|  Tools: log_workout, log_weight,     |
|         log_nutrition, read_sheet,   |
|         save_memory, read_memory,    |
|         upload_to_drive              |
+--------------------------------------+
       |
  +----+----------+
  v    v          v
Google  Local    Google
Sheets  Files    Drive
```

## Repository

Everything lives in one git repo: `/home/openclaw/lifeos/`

Auto-committed hourly via cron. Use `git log` to see full history.

```
/home/openclaw/lifeos/              <-- git repo root
|-- bot.py                          # The Telegram bot (entire application)
|-- soul.md                         # AI system prompt (personality, rules, sheet schemas)
|-- morning-brief.sh                # Daily 7am ET cron script (standalone, not part of bot)
|-- architecture.md                 # This file (system map for any AI/human)
|-- auto-commit.sh                  # Nightly git auto-commit script
|-- lifeos-bot.service              # systemd unit file (canonical copy)
|-- requirements.txt                # Python deps: openai, python-telegram-bot
|-- procedures.md                   # Expected tool call patterns per operation
|-- qa-check.sh                     # Daily integrity + procedure compliance check
|-- openclaw.env.example            # Env var template (no real secrets)
|-- .gitignore                      # Excludes logs/, uploads/, venv/
|-- memory/                         # AI-writable persistent state (markdown files)
|-- logs/                           # Conversation logs YYYY-MM-DD.jsonl (gitignored)
|-- uploads/                        # Telegram file uploads (gitignored)
+-- venv/                           # Python virtual environment (gitignored)
```

### What's tracked in git (auditable)
- All code (bot.py)
- All config (soul.md, service file, cron scripts)
- All AI memory files (memory/*.md)
- Architecture docs

### What's NOT in git (too large / ephemeral)
- logs/ — conversation JSONL files (kept on disk, not in repo)
- uploads/ — Telegram file uploads (pushed to Google Drive)
- venv/ — recreatable via `python3 -m venv venv && venv/bin/pip install -r requirements.txt`

## Components

### 1. Telegram Bot (`bot.py`)

The entire application. ~400 lines of Python that:
- Polls Telegram for messages from the authorized user (CHAT_ID from env)
- Sends messages to Grok 4.1 Fast (xAI) via OpenAI-compatible API with soul.md as system prompt
- Grok can call 7 tools: log_workout, log_weight, log_nutrition, read_sheet, save_memory, read_memory, upload_to_drive
- Tool results feed back to Grok until it produces a final text reply
- Replies sent back to Telegram
- All conversations logged to `logs/YYYY-MM-DD.jsonl`
- Handles text messages, file uploads (documents), and photo uploads
- `/clear` command resets conversation history

**Runtime:** Python 3.12 in venv at `/home/openclaw/lifeos/venv/`
**Dependencies:** `openai`, `python-telegram-bot`
**Runs as:** systemd service `lifeos-bot` under user `openclaw`
**Cost:** ~$0.50/month (Grok 4.1 Fast: $0.20/MTok in, $0.50/MTok out)

### 2. Morning Brief Cron (`morning-brief.sh`)

Standalone bash script, completely independent of the bot. Sends a daily Telegram message at 7am ET with:
- Today's workout from the routine
- Weight goal vs latest weigh-in (pulled from Google Sheets via gog)
- A motivational quote

**Schedule:** `CRON_TZ=America/Toronto 0 7 * * *` (root crontab)
**Dedup:** Lock file at `/tmp/morning-brief-YYYY-MM-DD.sent`

### 3. System Prompt (`soul.md`)

The AI's personality, rules, and context. Defines:
- Communication style (direct, data-driven, no filler)
- Approval rule (never change important files without the user saying APPROVE)
- Workout logging format and shorthand parsing
- Google Sheets column layouts for each tab
- Current goals, routine, and body stats
- Monthly audit framework
- DEXA scan extraction fields
- Google Drive upload procedures

Read by bot.py at startup. Edit this file to change the AI's behavior. Restart the bot after editing.

### 4. Auto-Commit (`auto-commit.sh`)

Runs hourly via cron. Commits any changes in the repo (memory files the bot writes, manual edits, etc.) with message `auto: daily snapshot YYYY-MM-DD`. Does nothing if no changes.

**Schedule:** `0 * * * *` (root crontab, every hour on the hour)
**Log:** `/home/openclaw/lifeos/auto-commit.log`

### 5. Google Sheets (source of truth for all metrics)

Spreadsheet ID: Set via `SHEET_ID` env var.

| Tab | Purpose | Columns |
|-----|---------|---------|
| Training Log | Workout data | Date, Exercise, Sets, Reps, Weight (lbs), RPE, Volume (lbs), Session Type, Data Source |
| Body Metrics | Daily weigh-ins | Date, Weight (lbs), Weight (kg), Body Fat %, Muscle Mass (kg), Water %, BMI, Data Source, Notes |
| Nutrition | Daily food intake | Date, Calories, Protein (g), Carbs (g), Fat (g), Fiber (g), Sodium (mg), Data Source, Notes |
| Recovery | Sleep/activity | Date, Sleep Score, Sleep Hours, Steps, Active Minutes, HRV, Resting HR, Data Source, Notes |
| Body Scans | DEXA results | Date, Scan Type, Total Body Fat %, Lean Mass (lbs/kg), Bone Density, VAT, Regional BF%, etc. |

Accessed via the `gog` CLI tool (path and account from env vars).

### 6. Google Drive (file uploads)

Folder and file IDs set via `DRIVE_UPLOADS_FOLDER` and `UPLOAD_INDEX_FILE_ID` env vars.

DEXA scans, progress photos, blood work uploaded via Telegram -> saved locally -> pushed to Drive.

## Configuration

All config is in `/opt/openclaw.env` (NOT in git). See `openclaw.env.example` for the template.

**To swap the AI model/provider**, change 3 env vars and restart:
- `AI_API_KEY` — API key for the AI provider
- `AI_BASE_URL` — API endpoint (e.g. `https://api.x.ai/v1`, `https://api.openai.com/v1`)
- `AI_MODEL` — Model name (e.g. `grok-4-1-fast`, `gpt-4o`, `claude-sonnet-4-6`)

Any provider with an OpenAI-compatible chat completions API works with zero code changes.

**Other env vars:**
- `TELEGRAM_BOT_TOKEN` — Telegram bot credentials
- `CHAT_ID` — Authorized chat ID
- `GOG_ACCOUNT` / `GOG_KEYRING_PASSWORD` — Google auth for gog CLI
- `SHEET_ID`, `DRIVE_UPLOADS_FOLDER` — Google resource IDs
- `LIFEOS_DIR`, `GOG_PATH` — path overrides

## Cron Jobs (root crontab)

| Schedule | Script | Purpose |
|----------|--------|---------|
| `0 7 * * *` ET | `morning-brief.sh` | Daily Telegram morning brief |
| `0 * * * *` | `auto-commit.sh` | Hourly git snapshot |
| `30 8 * * *` ET | `qa-check.sh` | Daily integrity check (alerts only on failure) |

## Service Management

```bash
systemctl status lifeos-bot      # Check status
journalctl -u lifeos-bot -f      # View live logs
systemctl restart lifeos-bot     # Restart after code changes
systemctl stop lifeos-bot        # Stop
```

## Conversation Logs

Every message exchange is saved to `logs/YYYY-MM-DD.jsonl`. Each line:

```json
{"ts": "2026-04-05T15:30:00", "user": "bench 225x5x3", "assistant": "Got it. Bench press..."}
```

## Change Tracking

- **Hourly auto-commit** catches all file changes (memory writes, soul.md edits, etc.)
- **Claude Code sessions** (terminal) are NOT automatically logged. Any AI making changes via terminal MUST commit with a descriptive message explaining what changed and why, before ending the session.
- **Telegram conversations** are logged to `logs/YYYY-MM-DD.jsonl` (gitignored — too large for repo, but kept on disk).
- `git log` is the audit trail. Use `git diff <commit>` to see exactly what changed.

## QA / Anti-Hallucination

Three layers, ordered by cost:

**Layer 1: Read-after-write verification (zero tokens, every write)**
Every tool that writes data (log_workout, log_weight, log_nutrition, save_memory) reads the data back immediately and appends `[VERIFIED]` or `[VERIFY FAILED]` to the tool result. The AI sees this. If it fails, the AI should tell the user.

**Layer 2: Daily integrity + procedure check (zero tokens, 8:30am ET cron)**
`qa-check.sh` runs daily and checks:
- Conversation log exists for today
- No `[VERIFY FAILED]` entries in today's log
- Yesterday's training was logged (unless rest day)
- Yesterday's nutrition was logged
- Weight logged in last 3 days
- Bot service is running
- Procedure compliance: did the bot read the right sheet tabs for the right operations?
- Architecture drift: are all expected files present? Is git healthy?

Sends a Telegram alert ONLY if issues are found. Silent if everything is fine.

**Layer 3: Tool audit trail (zero tokens, passive)**
Every conversation log entry includes a `tools` array showing exactly which tools were called, with what inputs, and what results. Any AI can compare "what the bot said it did" vs "what the tool log shows it actually did."

**Procedures:** `procedures.md` defines the expected tool call patterns for each operation (status reports, logging workouts, discussing body fat, etc.). If the bot consistently deviates from a procedure, that's a signal to reassess: maybe the procedure is wrong, not the bot. Update whichever is actually incorrect.

## Troubleshooting Rule

When debugging the bot's behavior from an external AI (e.g. Claude Code terminal):
1. **Ask the bot first.** Send it a message through its chat interface asking it to explain what it did and why. It can see its own system prompt, tool results, and reasoning — you can't.
2. Only then diagnose from the outside (check logs, sheet data, config, code).
3. This saves time and avoids guessing at root causes.

## How Another AI Should Pick Up This System

1. Read this file (`architecture.md`) for the full system map
2. Read `procedures.md` for expected tool call patterns and data source rules
3. Read `soul.md` for the AI personality, rules, and data schemas
4. Read `bot.py` for the implementation (~400 lines, self-contained)
4. Read files in `memory/` for persistent state
5. Read recent files in `logs/` for conversation history
6. Run `git log --oneline` to see change history
7. Run `gog sheets get <SHEET_ID> "<Tab>!A:Z"` to pull live data

## How to Recreate This System From Scratch

1. Clone/copy this repo to `/home/openclaw/lifeos/`
2. `python3 -m venv venv && venv/bin/pip install -r requirements.txt`
3. Copy `openclaw.env.example` to `/opt/openclaw.env` and fill in secrets
4. `cp lifeos-bot.service /etc/systemd/system/ && systemctl daemon-reload && systemctl enable --now lifeos-bot`
5. Set up crons: `crontab -e` and add the two cron entries from the table above
6. Authenticate gog: `gog auth login --account <email>`

## Architecture Audit (Monthly, 1st of each month)

A structured review of the entire system. Can be triggered anytime by the user saying "run an audit." The audit asks:

1. **Tools:** Are we using the best tools? Check for new releases, cheaper models, better APIs. Example: Claude Code added new features — does that replace anything we built?
2. **Cost:** What did we spend this month? Is there a cheaper model that performs equally? Are we wasting tokens anywhere?
3. **Errors:** Review QA alerts from the past month. Any patterns? Recurring procedure violations?
4. **Speed:** Are responses fast enough? Any tool calls timing out? Is the bot polling efficiently?
5. **Architecture:** Does the file structure still make sense? Any dead files? Any missing pieces?
6. **Deviations:** Did the bot consistently work around any procedures? If so, the procedure may be wrong.

Output: A report sent via Telegram + committed to git. All proposed changes follow the approval rule (APPROVE/REJECT/MODIFY).

The audit should be run by an AI (Claude Code or the bot) reading the actual data — logs, tool results, git history, cost estimates — not from memory.

## History

- **2026-04-03:** OpenClaw (Node.js gateway + Docker sandbox + Grok 4.1 fast) deployed
- **2026-04-05:** Replaced with LifeOS bot (single Python file). OpenClaw's sandbox had a `ModuleNotFoundError: No module named 'secrets'` bug preventing all file writes, plus unnecessary Docker/container complexity for a single-user bot.
- **2026-04-05:** Initially used Claude Sonnet ($12/mo), switched to Grok 4.1 Fast ($0.50/mo). The original Grok problems were caused by the broken sandbox, not the model.
- **2026-04-05:** Consolidated all files into single git repo with nightly auto-commit for full audit trail.
