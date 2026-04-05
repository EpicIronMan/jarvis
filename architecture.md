# J.A.R.V.I.S. — Architecture Document

Last updated: 2026-04-05

## Maintenance Rule

**Any AI or human that changes any file in this repo MUST update this file in the same session.** If the "Last updated" date is old, verify against the actual files before trusting this doc.

Every entry must include:
1. **What** the component does
2. **Why** it was built (what problem it solves)
3. **What it connects to** (what feeds it, what it feeds)

**When adding:** Document what the new component does, why it's needed, what feeds it, and what it feeds. Example: "Added sync_fitbit tool. Why: user wanted on-demand data pulls, not just 3x/day. Connects: Telegram → bot.py → fitbit_sync.py → Google Sheets."

**When removing:** Document what was removed, why, and what now handles its job. Example: "Removed X because Y now handles both X and Y's data. Y was updated to accept X's input format."

**When consolidating:** Document the removal AND the expanded responsibility. Don't just delete — explain what picks up the slack.

**When modifying connections:** Document the old flow and the new flow. Example: "Before: Renpho → separate script → Sheet. After: Renpho → Fitbit → fitbit_sync.py → Sheet. Why: eliminates a redundant pipeline."

**Pre/post QA for major changes:** Any major removal, cleanup, or restructuring MUST follow this pattern:
1. **Snapshot** — capture current state of all services, crons, auth, and key files
2. **Change** — perform the removal or restructuring
3. **Verify** — run the same snapshot checks and confirm everything still responds
4. **Alert** — send a confirmation to Telegram (or flag failures)
5. **Document** — update architecture.md with what was removed/changed and why

This applies to: deleting files or directories, removing services, stopping crons, changing data pipelines, restructuring folders, Docker cleanup, or anything that could break an existing connection. When in doubt, snapshot first.

**Why:** The OpenClaw-to-Jarvis migration and the orphan cleanup both used this pattern and caught issues (gog auth test initially failed post-cleanup). Without the verify step, that would have been a silent break discovered hours later.

**Coherence audits:** As features are added and removed, these notes accumulate and can become contradictory or stale. During the monthly audit (or anytime things feel unclear), review architecture.md for:
- Components mentioned that no longer exist
- Connections described that have been rerouted
- "Why" reasons that no longer apply
- Sections that contradict each other
If incoherence is found, flag it, investigate, and rewrite the affected sections. The doc must always reflect the current system accurately.

**Why this rule exists:** Without it, features get removed that shouldn't be (because nobody knows why they were there), or kept when they're redundant (because nobody knows what else covers it). As the system evolves, stale docs are worse than no docs — they mislead. This doc is the single source of truth for the entire system and must stay coherent.

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
Phone (Telegram)
       |
       v
Telegram Bot API (polling)
       |
       v
+--------------------------------------+
|  bot.py                              |  <-- Single Python file (~400 lines)
|  AI model via OpenAI-compatible SDK  |
|  Tools: log_workout, log_weight,     |
|         log_nutrition, read_sheet,   |
|         save_memory, read_memory,    |
|         upload_to_drive, sync_fitbit |
+--------------------------------------+
       |
  +----+----------+
  v    v          v
Google  Local    Google
Sheets  Files    Drive
  ^
  |
Fitbit API (3x/day auto-sync)
  ^
  |
Renpho scale --> Renpho app --> Fitbit
MyFitnessPal -----------------> Fitbit
```

## Data Flow

Data enters the system from these sources:

| Source | How it gets to Google Sheets | Frequency |
|--------|---------------------------|-----------|
| Renpho scale | Renpho app → Fitbit → fitbit_sync.py | Auto 3x/day (or on-demand via Telegram) |
| MyFitnessPal | MFP → Fitbit → fitbit_sync.py | Auto 3x/day (or on-demand via Telegram) |
| Fitbit (sleep, steps, HR) | fitbit_sync.py | Auto 3x/day (or on-demand via Telegram) |
| Workouts | User tells Jarvis on Telegram | Manual (user logs via chat) |
| DEXA scans | User uploads PDF to Telegram → Jarvis extracts | Manual (every few weeks) |
| Weight (manual) | User tells Jarvis on Telegram | Manual (backup if Renpho sync fails) |

All data lands in Google Sheets. Jarvis reads from the sheets — it never goes to Fitbit/Renpho/MFP directly. Each row includes a Notes column with sync timestamp (e.g. "synced 12:00 ET") so you know how fresh the data is.

**Why timestamps:** Without them, there's no way to know if a 175.3 lbs reading is from your morning weigh-in or stale data from yesterday's sync.

## Repository

Everything lives in one git repo: `/home/openclaw/lifeos/`

Auto-committed hourly via cron. Use `git log` to see full history.

```
/home/openclaw/lifeos/              <-- git repo root + GitHub mirror
|-- bot.py                          # The Telegram bot (entire application)
|-- soul.md                         # AI system prompt (personality, rules, sheet schemas)
|-- morning-brief.sh                # Daily 7am ET cron script (standalone, not part of bot)
|-- architecture.md                 # This file (system map for any AI/human)
|-- procedures.md                   # Expected tool call patterns per operation
|-- qa-check.sh                     # Daily integrity + procedure compliance check
|-- resolve.sh                      # CLI tool to mark QA issues as resolved
|-- resolved.jsonl                  # Log of resolved QA issues (checked before alerting)
|-- auto-commit.sh                  # Hourly git commit + push to GitHub
|-- lifeos-bot.service              # systemd unit file (canonical copy)
|-- requirements.txt                # Python deps: openai, python-telegram-bot
|-- openclaw.env.example            # Env var template (no real secrets)
|-- .gitignore                      # Excludes logs/, uploads/, venv/
|-- memory/                         # AI-writable persistent state (markdown files)
|-- logs/                           # Conversation logs YYYY-MM-DD.jsonl (gitignored)
|-- uploads/                        # Telegram file uploads (gitignored)
+-- venv/                           # Python virtual environment (gitignored)
```

**GitHub mirror:** github.com/EpicIronMan/jarvis (public, auto-pushed hourly)
**Why public:** Open source for community feedback and auditing. All personal info (IDs, keys, email) is in env file only — never in code or git history.

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
- AI can call 8 tools: log_workout, log_weight, log_nutrition, read_sheet, save_memory, read_memory, upload_to_drive, sync_fitbit
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

### 5. Fitbit Sync (`fitbit_sync.py` — external to this repo)

Automated data pipeline that pulls from Fitbit API and writes to Google Sheets 3x/day.

**Script:** `/home/openclaw/fitbit_sync.py`
**Config:** `/home/openclaw/.config/fitbit/fitbit_config.json`
**Tokens:** `/home/openclaw/.config/fitbit/tokens.json` (auto-refreshing OAuth2)
**Log:** `/home/openclaw/.config/fitbit/sync.log`
**Schedule:** systemd timer `fitbit-sync.timer` — 7am, 12pm, 10pm ET

**Data pulled:**
- Body Metrics tab: weight, body fat %, BMI (from Fitbit/Renpho scale)
- Recovery tab: sleep score, sleep hours, steps, active minutes, resting HR
- Nutrition tab: calories, macros (from MyFitnessPal → Fitbit sync)

**To trigger manually:** `systemctl start fitbit-sync.service`

This script is NOT in the Jarvis repo (it has its own credentials and config). It feeds the same Google Sheet that Jarvis reads from.

### 6. Google Sheets (source of truth for all metrics)

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

**Why this exists:** AI models can hallucinate — they may say "I logged your workout" without actually calling the tool, or pull body fat from the wrong sheet tab. We need to catch this without the user having to double-check everything manually. All QA is zero tokens (pure code/bash).

### Layer 1: Read-after-write verification (every write, zero tokens)

Every tool that writes data (log_workout, log_weight, log_nutrition, save_memory) reads the data back immediately and appends `[VERIFIED]` or `[VERIFY FAILED]` to the tool result. The AI sees the verification status and should tell the user if it failed.

**Why:** The OpenClaw sandbox bug showed that writes can silently fail. Read-after-write catches this at the moment it happens, not hours later.

### Layer 2: Tool audit trail (every message, zero tokens)

Every conversation log entry includes a `tools` array showing exactly which tools were called, with what inputs, and what results. Example:

```json
{"ts": "...", "user": "log bench 225x5x3", "assistant": "Logged!", "tools": [{"tool": "log_workout", "input": {...}, "result": "Logged 1 exercise [VERIFIED]"}]}
```

**Why:** If the bot says "I saved the routine and updated the changelog" but the tools array only shows one save_memory call, that's a caught hallucination. Any AI auditing the logs can flag the mismatch between claims and actions.

### Layer 3: Daily integrity + procedure check (8:30am ET, zero tokens)

`qa-check.sh` runs daily and checks:

| Check | What it catches | Why it matters |
|-------|----------------|----------------|
| Conversation log exists | Bot may be down or not receiving messages | Catches service outages |
| No `[VERIFY FAILED]` in logs | Writes that didn't land | Catches silent data loss |
| Yesterday's training logged | Missed workout logging | Data completeness |
| Yesterday's nutrition logged | Missed nutrition logging | Data completeness |
| Weight in last 3 days | Scale sync may be broken | Catches Fitbit/Renpho issues |
| Bot service running | Bot crashed | Catches service failures |
| Fitbit timer active | Fitbit sync may have stopped | Catches pipeline failures |
| Bot read Body Scans for BF% | Bot used wrong data source | Catches procedure violations |
| Save promises match tool calls | Bot hallucinated file saves | Catches hallucinations |
| Status reports read 3+ tabs | Bot gave incomplete report | Catches lazy data pulls |
| All expected files exist | Someone deleted a key file | Catches architecture drift |
| Git repo healthy | Auto-commit may be broken | Catches backup failures |

**Why procedure checks:** The bot should follow specific tool call patterns (defined in `procedures.md`). Example: when discussing body fat, it MUST read the Body Scans tab (DEXA data), NOT the Body Metrics tab (Renpho data). The QA catches when it takes shortcuts.

### Layer 4: Resolution tracking (zero tokens)

`resolved.jsonl` stores issues that have been fixed. The QA script checks this file before alerting — if an issue key is already resolved, it skips it.

**Why:** Without this, the QA keeps alerting on the same fixed problem forever. Wastes attention and causes alert fatigue. When a fix is applied, log it:

```bash
./resolve.sh "fitbit_sync_auth" "Fixed by running script directly instead of systemctl"
```

Each entry has: issue key, what fixed it, and the date. If the same issue reappears after a fix (meaning the fix didn't hold or a new change broke it), date-specific keys (like `no_training_2026-04-06`) won't match old resolutions, so it alerts again.

**Why "tentative" resolution:** A fix might work today but break tomorrow if another change conflicts with it. The resolved file is a record of what was tried. If the QA flags the same pattern again, an AI can check the resolved file to see what was already attempted — avoiding chasing the same dead end twice.

### Deviation handling

If the bot consistently does something outside the defined procedures:
1. QA flags it in the daily alert
2. The user reviews with an AI (Claude Code, the bot itself, or both)
3. Discussion: is the procedure wrong, or is the bot wrong?
4. The user decides: update the procedure, fix the bot, or leave it
5. Changes committed with reasoning in the git message

**Why not auto-fix:** Deviations are signals, not bugs. Sometimes the bot found a better path and the procedure should be updated. Only the user decides.

### Procedures (`procedures.md`)

Defines the expected tool call patterns for each operation — which sheet tab for which data, what tools should be called for a status report, etc. This is the "correct path" that QA checks against.

**Why it's a separate file:** Keeps architecture.md focused on the system map. procedures.md is the operational rulebook that changes more frequently as we learn what works.

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

1. **Documentation coherence:** Read architecture.md end to end. Are there contradictions? Components mentioned that no longer exist? Connections that have been rerouted but the old description remains? Fix any incoherence first — everything else depends on accurate docs.
2. **Tools:** Are we using the best tools? Check for new releases, cheaper models, better APIs. Example: Claude Code added new features — does that replace anything we built?
3. **Cost:** What did we spend this month? Is there a cheaper model that performs equally? Are we wasting tokens anywhere?
4. **Errors:** Review QA alerts from the past month. Any patterns? Recurring procedure violations? Check resolved.jsonl — are old fixes still holding?
5. **Speed:** Are responses fast enough? Any tool calls timing out? Is the bot polling efficiently?
6. **Architecture:** Does the file structure still make sense? Any dead files? Any missing pieces?
7. **Orphan check:** Look for:
   - Features or scripts that nothing connects to (orphaned code)
   - Empty directories or files with no content
   - Deeply nested folders that could be flattened (3 levels deep to reach 2 files = consolidate)
   - Services or crons still running for components that were removed
   - Env vars that no code references anymore
   - Memory files the bot wrote but never reads back
   Consolidate or eliminate anything that isn't serving a purpose.
8. **Deviations:** Did the bot consistently work around any procedures? If so, the procedure may be wrong.

Output: A report sent via Telegram + committed to git. All proposed changes follow the approval rule (APPROVE/REJECT/MODIFY).

The audit should be run by an AI (Claude Code or the bot) reading the actual data — logs, tool results, git history, cost estimates — not from memory.

## History

Each entry explains what changed AND why — so future audits can assess whether the reason still applies.

- **2026-04-03:** OpenClaw (Node.js gateway + Docker sandbox + Grok 4.1 fast) deployed
- **2026-04-05:** Replaced OpenClaw with single Python file (`bot.py`). **Why:** OpenClaw's sandbox had a `ModuleNotFoundError: No module named 'secrets'` bug preventing all file writes. Docker sandbox, container system, and gateway abstraction were unnecessary complexity for a single-user bot.
- **2026-04-05:** Initially used Claude Sonnet ($12/mo), switched to Grok 4.1 Fast ($0.50/mo). **Why:** Grok's problems were caused by the broken sandbox, not the model itself. With direct file access, Grok 4.1 works well at 24x lower cost.
- **2026-04-05:** Made all config env-driven (AI_API_KEY, AI_BASE_URL, AI_MODEL, CHAT_ID, etc.). **Why:** Swap AI provider, chat platform, or Google resources by changing env vars, not code. Platform-agnostic by design.
- **2026-04-05:** Injected current date/time into system prompt dynamically. **Why:** Grok had no clock — it was guessing day-of-week wrong (mapped Saturday to Wednesday). Now every message includes "Current date/time: Sunday, 2026-04-05 4:49 PM ET".
- **2026-04-05:** Added read-after-write verification on all tool writes. **Why:** OpenClaw proved writes can silently fail. Verification catches this immediately.
- **2026-04-05:** Added tool audit trail to conversation logs. **Why:** The bot said it would update CHANGELOG.md but only called save_memory once. The tool log catches claims vs actual actions.
- **2026-04-05:** Added daily QA check (qa-check.sh). **Why:** Catches data gaps, procedure violations, service outages, and architecture drift — all at zero token cost.
- **2026-04-05:** Added procedures.md. **Why:** Defines the "correct path" for each operation so QA can check compliance. If the bot deviates, we discuss whether the procedure or the bot is wrong.
- **2026-04-05:** Added resolution tracking (resolved.jsonl + resolve.sh). **Why:** QA was flagging the same fixed issues repeatedly. Resolution log lets QA skip known fixes and avoid alert fatigue.
- **2026-04-05:** Added sync_fitbit tool for on-demand data pulls. **Why:** Fitbit syncs 3x/day but user wanted fresh data on demand. Fixed auth issue (bot couldn't call systemctl, now runs script directly).
- **2026-04-05:** Added sync timestamps to Fitbit data (Notes column). **Why:** Without timestamps, no way to know if data is from today's weigh-in or yesterday's stale sync.
- **2026-04-05:** Rebranded to J.A.R.V.I.S., scrubbed all personal info, squashed git history, pushed to GitHub (public). **Why:** Open source for community review. Personal info (email, IDs, keys) stays in env file only.
- **2026-04-05:** Consolidated into single git repo with hourly auto-commit + auto-push to GitHub. **Why:** Full audit trail. Any AI can run `git log` to see every change and why it was made.
- **2026-04-05:** Orphan cleanup. Removed: old `/home/openclaw/lifeos-bot/` directory (stale duplicate), Docker sandbox container + images (99MB, OpenClaw only), OpenClaw directories (agents, canvas, cron, devices, identity, logs, media, sandbox, tasks, telegram, credentials), stale workspace files (old SOUL.md, CHANGELOG.md, etc.). Kept: `.openclaw/workspace/homebrew/` (gog binary), `.openclaw/workspace/.config/gogcli/` (Google auth). **Why:** ~100MB of dead weight serving no purpose. **QA approach:** Snapshot all service states before cleanup → clean → verify same services still respond → send Telegram confirmation.
