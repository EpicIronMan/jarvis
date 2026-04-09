# J.A.R.V.I.S. — Architecture Document

Last updated: 2026-04-08

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

## Core Principles (in priority order)

**1. Integrity** — Data must be correct, complete, and verifiable. No point in being fast or cheap if the data is wrong, writes silently fail, or the AI hallucinates actions. Every write is verified. Every tool call is logged. QA runs daily.

**2. Reliability** — The system must not break. Changes are snapshot-tested (before/after QA). Procedures are documented so any AI can follow them. Resolution tracking prevents chasing fixed problems. Architecture is audited monthly for coherence.

**3. Efficiency** — Minimize tokens, code, files, and complexity — but never at the expense of #1 or #2. Specifically:
- Use zero-token solutions (bash scripts) over AI calls wherever possible
- Keep the codebase small (one file bot, not a framework)
- Don't create files that nothing reads
- Don't add features that duplicate existing ones
- Use the cheapest AI model that achieves the required quality
- Env-driven config over hardcoded values (swap, don't rewrite)

**When integrity and efficiency conflict, integrity wins.** Example: read-after-write verification costs an extra Google Sheets API call per write. That's "inefficient" — but without it, we can't trust the data landed. So we keep it.

**When evaluating any change, ask in order:**
1. Does this maintain data integrity? (if no, stop)
2. Does this maintain reliability? (if no, reconsider)
3. Is this the most efficient way to achieve #1 and #2? (if no, simplify)

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
| DEXA scans | User uploads PDF to Telegram → pdf2image converts to page images → AI reads via vision | Manual (every few weeks) |
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
|-- (procedures.md removed 2026-04-07 — consolidated into soul.md)
|-- qa-check.sh                     # Daily integrity + procedure compliance check
|-- resolve.sh                      # CLI tool to mark QA issues as resolved
|-- resolved.jsonl                  # Log of resolved QA issues (checked before alerting)
|-- decisions.log                   # Append-only decision log (why-this-over-that)
|-- daily-audit-template.md         # End-of-day Claude Code audit checklist
|-- claude-sessions/                # Claude Code session summaries (for retrieval after terminal drops)
|-- qa-hits.jsonl                   # QA check hit tracking (fed into monthly audit)
|-- auto-commit.sh                  # Hourly git commit + push to GitHub
|-- lifeos-bot.service              # systemd unit file (canonical copy)
|-- requirements.txt                # Python deps: openai, python-telegram-bot
|-- openclaw.env.example            # Env var template (no real secrets)
|-- soul-proposals.jsonl             # Pending/processed soul.md change proposals
|-- review-soul-proposals.py        # Daily reviewer for soul proposals (8pm ET cron)
|-- audit-state.json                # Bookmark state for audit tiers (daily/weekly/monthly)
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

The entire application. ~1,035 lines of Python. Single agent, single model, single conversation.

**Architecture:** One AI agent handles everything — daily chat, logging, research, calorie calculations, trend analysis. No mode switching, no dual-agent, no conversation filtering. The model reasons about what to do and uses tools to do it.

**Model:** Configurable via env vars (`AI_MODEL`, `AI_BASE_URL`, `AI_API_KEY`). Currently Grok 4.20 via xAI API. Swap to any OpenAI-compatible provider by changing env vars.

**Agent identity:** `AGENT_NAME` and `AGENT_EMOJI` env vars. Default: J.A.R.V.I.S. / 🤖. Change name without touching code.

**15 tools:** log_workout, log_cardio, log_weight, log_nutrition, read_sheet, write_sheet, clear_row, save_memory, propose_soul_change, read_memory, upload_to_drive, list_drive, download_from_drive, read_pdf, sync_fitbit

**Monitoring (passive — flags issues, never intervenes):**
- `_append_failure_notice` — if tool errors aren't surfaced in reply
- `_append_write_hallucination_notice` — if bot claims write with no write tool call
- `_clean_content` — strips model-generated name prefixes and bad markdown
- `_escape_markdownv2` — escapes special chars for Telegram rendering
- `_send_reply` — shared send logic across all handlers (monitoring → log → escape → send)

**Logging:** All conversations to `logs/YYYY-MM-DD.jsonl` with model name per entry. Full conversation reload on restart.

**Formatting:** MarkdownV2 for bold rendering. No markdown headers, no triple asterisks — code strips them.

**Runtime:** Python 3.12 in venv at `/home/openclaw/lifeos/venv/`
**Dependencies:** `openai`, `python-telegram-bot`, `pdf2image`, `Pillow`
**System dependency:** `poppler-utils` (for PDF→image conversion)
**Runs as:** systemd service `lifeos-bot` under user `openclaw`
**Cost:** Grok 4.20 ~$2/$6 per MTok. Plan to test cheaper models (GPT-4.1-mini) once architecture is proven stable.

### 2. Morning Brief Cron (`morning-brief-ai.py`)

AI-powered morning brief, completely independent of the bot. Sends a daily Telegram message at 7am ET with:
- Today's workout from the routine
- Weight goal vs latest weigh-in (pulled from Google Sheets via gog)
- Nutrition/recovery summary
- Pending soul proposals count (reminds user to review if >0)
- A motivational line

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
| Body Scans | DEXA results | Date, Scan Type, Total Body Fat %, Lean Mass (lbs), Lean Mass (kg), Bone Density (g/cm²), Visceral Fat Area (cm²), Trunk Fat %, Arms Fat %, Legs Fat %, Renpho BF% Same Week, DEXA-Renpho Offset, Data Source, Source File, RMR (cal/day), Notes |

Accessed via the `gog` CLI tool (path and account from env vars).

**Notes convention:** Every tab has a Notes column. Notes explain *why* data was written or changed — they are context for any AI or human reading the sheet later. Examples: "synced 12:00 ET", "Added RMR — extracted from DEXA PDF 2026-04-02", "Corrected BF% from PDF ground truth". When the bot writes data via `write_sheet`, it must include a reason that gets logged in Notes. These notes are part of the audit trail — never delete them.

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
| `0 9 1 * *` ET | `monthly-audit.sh` | Monthly architecture audit report |

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

| # | Check | What it catches | Why it matters |
|---|-------|----------------|----------------|
| 1 | Conversation log exists | Bot may be down or not receiving messages | Catches service outages |
| 2 | No `[VERIFY FAILED]` in logs | Writes that didn't land | Catches silent data loss |
| 3 | Yesterday's training logged | Missed workout logging (skips Sunday) | Data completeness |
| 4 | Yesterday's nutrition logged | Missed nutrition logging | Data completeness |
| 5 | Weight in last 3 days | Scale sync may be broken | Catches Fitbit/Renpho issues |
| 6 | Bot service running | Bot crashed | Catches service failures |
| 7 | Fitbit timer active | Fitbit sync may have stopped | Catches pipeline failures |
| 8a | Bot read Body Scans for BF% | Bot used wrong data source | Catches procedure violations |
| 8b | Save promises match tool calls | Bot hallucinated file saves | Catches hallucinations |
| 8c | Status reports read 3+ tabs | Bot gave incomplete report | Catches lazy data pulls |
| 20 | Tool result errors not surfaced | Bot said "saved" but tool returned Permission denied or ERROR | Catches silent failures |
| 21 | Memory file permissions | memory.md not owned by openclaw — bot can't write | Catches permission drift |
| 22 | Said-vs-did (log/save claims vs tool calls) | Bot claimed to log/save but no matching tool call exists | Catches action hallucinations |
| 23 | Exercise count mismatch | Bot discussed logging exercises but no log_workout calls found | Catches missed logging |
| 24 | Stale soul proposals | >5 pending/awaiting proposals in soul-proposals.jsonl | Catches review pipeline failures |
| 9a | Empty directories | Orphaned folders from old features | Orphan detection |
| 9b | Old openclaw service enabled | Forgotten service still running | Orphan detection |
| 9c | Stale memory files (30d+) | Dead memory no one references | Orphan detection |
| 10 | Expected files exist | Core file accidentally deleted | Architecture drift |
| 11 | Git repo healthy | Repo broken or auto-commit failing | Backup integrity |
| 12 | Morning brief delivered | Cron ran but AI/Telegram failed | Silent delivery failure |
| 13 | Disk space (<85%) | Box filling up | Infrastructure health |
| 14 | RAM usage (<85%) | OOM risk | Infrastructure health |
| 15 | Fitbit data freshness (2d) | Timer runs but sync silently fails | Data pipeline health |
| 16 | Google Sheets auth | gog token expired | Data pipeline health |
| 17 | Caddy web server | Web endpoint down or unresponsive | Infrastructure health |
| 18 | Sleep data freshness (2d) | Ring/watch not worn, stale recovery data | Data completeness |
| 19 | Git remote reachable | Pushes silently failing, no backup | Backup integrity |

All hits are logged to `qa-hits.jsonl` for the monthly effectiveness audit.

**Why procedure checks:** The bot should follow specific tool call patterns (defined in `soul.md` under "Data Sources"). Example: when discussing body fat, it MUST read the Body Scans tab (DEXA data), NOT the Body Metrics tab (Renpho data). The QA catches when it takes shortcuts.

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

### Procedures (consolidated into `soul.md` on 2026-04-07)

Previously a separate file (`procedures.md`). Consolidated into soul.md because having operational rules in multiple files caused drift — the bot would follow one file's rules while violating another's. Now soul.md is the single source of truth for all bot behavior, data source rules, and operational patterns.

### Soul Proposal Pipeline

**What:** A governance layer for soul.md changes. Instead of the bot telling the user "have Claude Code update soul.md," it writes a structured proposal to `soul-proposals.jsonl`. An AI reviewer checks for conflicts/redundancy, then the user approves or rejects via Telegram.

**Why:** soul.md is the bot's behavioral core. Uncontrolled edits risk breaking established rules. The "tell the user" pattern lost directives (user forgets, context lost). The pipeline captures immediately, reviews for conflicts, and keeps the user as final authority.

**Flow:**
```
User gives directive → Bot calls propose_soul_change → soul-proposals.jsonl (status: pending)
                                                              |
Evening audit → Claude Code reviews all pending proposals → presents to user
                                                              |
User says APPROVE/REJECT → Claude Code edits soul.md (placed in correct section)
```

**Routing logic (in soul.md):** The bot distinguishes between soul material (behavioral rules, algorithms, communication style) and memory material (facts, preferences, decisions). When unsure, defaults to memory — easier to promote later.

**Audit (Section 5.5 in daily-audit-template.md):** Three tiers verify routing correctness:
- Daily: incremental log read from bookmark, check each directive was routed correctly
- Weekly: 7-day pattern scan for repeated instructions, inconsistent rule-following
- Monthly: deep review comparing soul.md against actual usage, dead rules, drift

**Connects to:**
- `bot.py` — propose_soul_change tool writes proposals
- `soul.md` — Claude Code applies approved proposals here + routing logic in "Where Things Go"
- `morning-brief-ai.py` — pending count shown in morning brief
- `daily-audit-template.md` — Section 5.5 reviews proposals and verifies routing correctness
- `qa-check.sh` — Check 24 flags >5 stale proposals
- `audit-state.json` — bookmark tracking for tiered audits

**Files:**
- `soul-proposals.jsonl` — append-only proposal log with status tracking
- `review-soul-proposals.py` — standalone reviewer (can be run manually, not cron'd)
- `audit-state.json` — daily/weekly/monthly audit bookmarks

## Troubleshooting Rule

When debugging the bot's behavior from an external AI (e.g. Claude Code terminal):
1. **Ask the bot first.** Send it a message through its chat interface asking it to explain what it did and why. It can see its own system prompt, tool results, and reasoning — you can't.
2. Only then diagnose from the outside (check logs, sheet data, config, code).
3. This saves time and avoids guessing at root causes.

## How Another AI Should Pick Up This System

1. Read this file (`architecture.md`) for the full system map
2. Read `soul.md` for the AI personality, rules, data sources, and operational patterns
3. Read `bot.py` for the implementation (self-contained)
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

## Architecture Audit (Monthly, 1st of each month at 9am ET)

`monthly-audit.sh` runs automatically and sends a Telegram report with: git activity, QA summary, resolved issues, memory file health, service status, disk usage, orphan check, and recent changes. Zero tokens — pure bash data gathering.

The report ends with a review checklist. The user replies to Jarvis (or opens Claude Code) to discuss any findings — that's when tokens are used, and only if needed.

Can also be triggered anytime by saying "run an audit" to Jarvis or running `./monthly-audit.sh` manually.

The audit should review:

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
8. **Context gaps:** Are there questions the bot consistently can't answer that it should? This means the system prompt or injected context is missing something. Example: the bot couldn't provide the Google Sheet link because SHEET_ID was only used internally by tools — the AI never saw it. Fix: inject it into the system prompt.
9. **Stale data:** Is the latest date in key sheet tabs (Body Metrics, Nutrition, Recovery) within the last 24 hours? If not, the sync or read logic may be broken.
10. **Deviations:** Did the bot consistently work around any procedures? If so, the procedure may be wrong.

Output: A report sent via Telegram + committed to git. All proposed changes follow the approval rule (APPROVE/REJECT/MODIFY).

The audit should be run by an AI (Claude Code or the bot) reading the actual data — logs, tool results, git history, cost estimates — not from memory.

**Audit improvement rule:** Every time an issue is fixed, ask: "Would the audit have caught this?" If not, add a check. The audit gets smarter from real problems, not guesses.

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
- **2026-04-05:** Added procedures.md. **Why:** Defines the "correct path" for each operation so QA can check compliance. (Consolidated into soul.md on 2026-04-07 — separate file caused instruction drift.)
- **2026-04-05:** Added resolution tracking (resolved.jsonl + resolve.sh). **Why:** QA was flagging the same fixed issues repeatedly. Resolution log lets QA skip known fixes and avoid alert fatigue.
- **2026-04-05:** Added sync_fitbit tool for on-demand data pulls. **Why:** Fitbit syncs 3x/day but user wanted fresh data on demand. Fixed auth issue (bot couldn't call systemctl, now runs script directly).
- **2026-04-05:** Added sync timestamps to Fitbit data (Notes column). **Why:** Without timestamps, no way to know if data is from today's weigh-in or yesterday's stale sync.
- **2026-04-05:** Rebranded to J.A.R.V.I.S., scrubbed all personal info, squashed git history, pushed to GitHub (public). **Why:** Open source for community review. Personal info (email, IDs, keys) stays in env file only.
- **2026-04-05:** Consolidated into single git repo with hourly auto-commit + auto-push to GitHub. **Why:** Full audit trail. Any AI can run `git log` to see every change and why it was made.
- **2026-04-06:** Added PDF vision reading + Google Drive browsing. PDFs are converted to page images (pdf2image + poppler) and sent as multimodal vision content to the AI. Reads 5 pages at a time — if the AI needs more, it calls `read_pdf` again with the next page range (uses the existing tool loop). Also added `list_drive` and `download_from_drive` tools so the bot can browse any Google Drive folder and read files it finds (DEXA scans, blood work, etc.) without the user re-uploading. Files are cached locally after first download. 20MB size guard on downloads. **Why:** The bot claimed to "extract" DEXA data from PDFs but couldn't — it only saved the file path. Text extraction (pdfplumber) would be cheaper but less reliable for formatted reports with tables/graphics. Vision is more accurate (integrity > efficiency). Drive browsing lets the bot read old files and files the user drops into any Drive folder manually. New deps: `pdf2image`, `Pillow`, `poppler-utils`.
- **2026-04-06:** System timezone set to America/Toronto (was UTC). **Why:** `CRON_TZ` variable was silently ignored by Vixie Cron — morning brief was firing at 7am UTC (3am ET) instead of 7am ET. Removed now-unnecessary `CRON_TZ` lines from crontab. All cron jobs (morning-brief, auto-commit, qa-check, monthly-audit) now run in ET natively.
- **2026-04-06:** Fixed `grep -c || echo "0"` bug in qa-check.sh. **Why:** `grep -c` outputs "0" AND exits non-zero on no-match, so `|| echo "0"` appended a second "0", producing "0\n0" which broke integer comparisons. Changed to `|| true`. Also added index.lock retry for git health check to avoid false alarms from auto-commit race conditions.
- **2026-04-06:** Switched AI model from Grok 4.1 Fast to Grok 4.20. **Why:** Hallucination concerns with the cheaper model. Cost impact needs monitoring — 4.1 Fast was ~$0.50/mo, 4.20 pricing TBD but significantly higher based on $2-3 spend in first 2 days.
- **2026-04-06:** Expanded QA from 11 to 19 checks. Added: morning brief delivery (12), disk space (13), RAM (14), Fitbit data freshness (15), Google Sheets auth (16), Caddy health (17), sleep data freshness (18), git remote reachable (19). **Why:** These are all failure modes that break silently — you wouldn't know until you noticed stale data or a missing brief. Also added hit tracking (`qa-hits.jsonl`) so the monthly audit can report which checks fire often (valuable) vs never (candidates for removal).
- **2026-04-06:** Added decisions.log — append-only decision log capturing options considered, what was chosen, and why. **Why:** architecture.md changelog captures *what* changed; decisions.log captures *why this over that*. Backfilled key decisions from 2026-04-05 and 2026-04-06. Monthly audit counts entries.
- **2026-04-06:** Added QA effectiveness audit to monthly-audit.sh. **Why:** QA checks should be audited too — if a check never fires in 3 months, it's either perfectly reliable (good) or the check is broken (bad). Monthly review surfaces this. Includes recommendation notes for checks flagged as potentially low-value (9a, 9b, 8b).
- **2026-04-06:** Removed anti-hallucination response stripping from conversation reload. Bot now loads its own full responses on restart, not just user messages with placeholders. **Why:** The stripping meant the bot didn't know what it already did or committed to after a restart. Hallucination risk is now mitigated by the daily QA audit (checks 20-23) and end-of-day Claude Code audit instead. Full context = bot knows what it logged, what it promised, and what failed.
- **2026-04-06:** Fixed memory.md ownership (was root:root, now openclaw:openclaw). **Why:** Bot runs as openclaw but couldn't write to memory.md — every save_memory call silently failed. Bot told user saves succeeded when they didn't.
- **2026-04-06:** Updated soul.md routine: Seated Cable Rows → Cable Rows. **Why:** User approved routine swap on 2026-04-06 due to back issues. Memory save failed (permission bug), soul.md was stale.
- **2026-04-06:** Added QA checks 20-23 (silent tool errors, memory permissions, said-vs-did, exercise count mismatch). **Why:** Today's audit revealed the bot claimed actions it never took and hid tool errors. These checks catch those failures daily.
- **2026-04-06:** Added daily-audit-template.md — end-of-day Claude Code audit checklist. **Why:** Bash QA catches mechanical failures; the daily audit catches reasoning errors, logic mistakes, and memory retention issues. Template covers: said-vs-did, logic check, memory retention, compliance, data integrity, backfills, model intuition tracking, and guardrail decisions.
- **2026-04-06:** Added multi-agent mode switching to bot.py. Admin mode (GPT-4.1-nano) handles daily ops; Research mode (Grok 4.20-reasoning) handles deep reasoning, calorie math, exercise science. User switches with "switch to research"/"switch back". Research replies prefixed with 🔬. Code-level guardrail: if admin mode outputs calorie/MET estimates without using research tool, auto-appends warning suggesting research mode. Logs record both `model` and `mode` for audit. **Why:** Admin model shouldn't guess research answers. Grok 4.20 is better at factual reasoning but expensive — only used when needed. User controls the switch, bot suggests it.
- **2026-04-06:** Added tool failure safety net to bot.py. Two layers: (1) `execute_tool` returns emphatic error instructing AI to tell the user, (2) `_append_failure_notice()` auto-appends failure notice if bot's reply doesn't mention tool errors. Applied to all three handlers (text, document, photo). **Why:** Bot told user "saved" when save_memory returned Permission denied. Model saw the error but ignored it. Code-level safety net makes the system self-correcting without adding model instructions.
- **2026-04-06:** Three architectural fixes to dual-agent system. (1) **Conversation filtering** (`_filter_conversation`): each agent now only sees its own responses as `role: assistant`; cross-mode responses become `[Other Agent said]: ...` in user role; handoff prompts stripped entirely. Root cause: both agents shared one conversation stream, so each saw the other's responses as their own words — caused identity confusion, mode hallucinations, and stale-question answers. (2) **One-shot escalation**: cardio auto-switch, write escalation, and mode hallucination detection now use research model for a single response without changing `chat_mode`. Previously they set mode to "research" permanently, so the user got silently stuck in research mode. (3) **Agent names to config**: `ADMIN_AGENT_NAME`, `RESEARCH_AGENT_NAME`, `*_SWITCH_KEYWORDS` are now env vars. All system prompts, regexes, response strings, and mode detection derive from these constants. soul.md uses generic language. Rename agents or swap models via env vars, no code changes. **Why:** 5pm-9pm session showed: mode switching failing on typos, admin hallucinating mode switches 6+ times, research answering old FFMI question when user asked about calories, bot silently stuck in research mode after auto-escalation. User correctly diagnosed that the models work fine in a clean chat window — the problem was the conversation architecture feeding mixed identities. **Connections:** `_filter_conversation`, `_detect_mode_switch`, `ask_ai` (is_handoff param), all handlers, config constants block, soul.md.
- **2026-04-06:** Swapped admin model from Grok 4.1 Fast Reasoning to GPT-4.1-nano ($0.10/$0.40). **Why:** Grok repeatedly hallucinated tool calls (said "saved"/"logged" without calling tools). Nano actually calls tools. Added model field to conversation logs for A/B comparison.
- **2026-04-06:** Added `clear_row` tool for blanking sheet rows. Added row numbers to `read_sheet` output (e.g. "Row 16: ...") so bot can target correct rows for clear/write. **Why:** Bot cleared wrong row because `read_sheet` returned sorted data with no row positions. Also: Grok 4.1 cleared row 3 (Leg Curls from 2026-04-04) by mistake — data unrecoverable, no April 4 logs exist.
- **2026-04-06:** Added `research` tool — calls Grok 4.20 (grok-4.20-0309-reasoning) for deep reasoning tasks. Used for calorie/MET calculations, exercise science, nutrition research. Admin model (nano) handles tool calling; research model handles factual accuracy. Results should be cached in memory/Notes. **Why:** Admin model shouldn't guess at research — wrong MET value (7 instead of ~4) produced 320cal instead of ~150-200cal.
- **2026-04-06:** Added Cardio tab to Google Sheet + `log_cardio` tool to bot.py. Columns: Date, Exercise, Duration (min), Speed, Incline, Net Calories, MET Used, Data Source, Notes. Separate from Training Log to keep schemas clean. **Why:** Bot was hacking cardio into `log_workout` (reps=minutes, weight=speed), producing garbage data. Cardio needs duration/speed/incline/calories, not sets/reps/weight. Updated `read_sheet` available tabs to include Cardio.
- **2026-04-06:** Saved workout logging decisions to memory.md: varying reps → multi-row, unilateral → per-side labels, cardio algorithm (net calories, MET formula, step overcount, caching rules). **Why:** These were agreed in conversation but never persisted due to the permission bug. Without them, the bot would forget these decisions every new day.
- **2026-04-07:** Consolidated procedures.md into soul.md. **Why:** Operational rules were scattered across soul.md, procedures.md, memory.md, and bot.py tool descriptions — they drifted apart and contradicted each other (e.g. soul.md said "log immediately" while tool description said "wait for confirmation"). Now soul.md is the single source of truth for all bot behavior. memory.md is only for user decisions (routine changes, approvals). procedures.md deleted.
- **2026-04-07:** Added "How You Think" section to soul.md — data integrity principles, self-verification standard. **Why:** Bot was making basic reasoning mistakes (date hallucination, inconsistent calculations, not verifying writes) because soul.md had specific rules but no general reasoning principles. The model followed rules mechanically instead of thinking critically.
- **2026-04-07:** Added "Where Things Go" section to soul.md. **Why:** Bot was saving operational rules to memory.md instead of soul.md, causing fragmentation. Now the bot knows: soul.md = behavioral rules, memory.md = user decisions, decisions.log = tradeoffs.
- **2026-04-07:** Fixed conversation reload to include tool history. **Why:** `load_conversation_from_logs()` only loaded user/assistant text, stripping tool calls and results. After a restart, the model had no idea what it actually did vs what it said — couldn't self-verify across restarts.
- **2026-04-07:** Fixed sheet append column drift. Changed from INSERT_ROWS to OVERWRITE mode for all gog sheets append calls. **Why:** INSERT_ROWS combined with blank rows in the sheet caused data to land 5+ columns to the right. Every April 7 workout was misaligned. Also fixed `_verify_sheet_write` to check column position (date in col A, field in col B) instead of just string presence anywhere in the row — the old check returned [VERIFIED] for misaligned data.
- **2026-04-07:** Added empty response retry and 429 rate limit backoff to ask_ai(). **Why:** Grok returned empty content (user saw blank messages) and 429 errors (raw error string dumped to user). These are API-level failures the model can't self-correct — code handling required. Retries once on empty, backs off 30/60/120s on 429.
- **2026-04-07:** Removed workout approval step. **Why:** Extra round-trip that got missed or caused friction. Bot now logs immediately and shows what was logged — user corrects if needed. Updated soul.md, bot.py tool description, and procedures.md (before deletion).
- **2026-04-07:** Switched AI model from Grok 4.20 ($2/$6) to grok-4-1-fast-reasoning ($0.20/$0.50). **Why:** The issues today were model laziness (not verifying output, inconsistent math), not capability. With soul.md reasoning principles, tool history in conversation reload, and code-level API failure handling, the safety net is strong enough for the cheaper model. 10x cost reduction. Reversible via env var.
- **2026-04-05:** Orphan cleanup. Removed: old `/home/openclaw/lifeos-bot/` directory (stale duplicate), Docker sandbox container + images (99MB, OpenClaw only), OpenClaw directories (agents, canvas, cron, devices, identity, logs, media, sandbox, tasks, telegram, credentials), stale workspace files (old SOUL.md, CHANGELOG.md, etc.). Kept: `.openclaw/workspace/homebrew/` (gog binary), `.openclaw/workspace/.config/gogcli/` (Google auth). **Why:** ~100MB of dead weight serving no purpose. **QA approach:** Snapshot all service states before cleanup → clean → verify same services still respond → send Telegram confirmation.
- **2026-04-08:** Added soul proposal pipeline. Bot calls `propose_soul_change` tool to file proposals to `soul-proposals.jsonl`. Claude Code reviews pending proposals during daily audit (Section 5.5) and applies approved changes to soul.md. Bot never writes to soul.md directly. **Why:** "Tell the user to have Claude Code update soul.md" pattern lost directives — user forgets between sessions. Pipeline captures immediately, Claude Code reviews for conflicts/quality, user approves. soul.md routing logic added to "Where Things Go" section — bot distinguishes between behavioral rules (soul proposals) and facts/preferences (memory). **Connections:** bot.py (propose_soul_change tool), soul.md (routing logic + approved proposals), soul-proposals.jsonl (proposal queue), daily-audit-template.md (Section 5.5 reviews proposals + routing), morning-brief-ai.py (pending count), qa-check.sh (Check 24 flags stale proposals).
- **2026-04-08:** Expanded daily audit template. Added Section 5.5A1 (intent vs action — did bot understand what user actually meant), expanded 5.5C (cross-reference decisions.log for re-litigated or revisitable decisions), added Section 10 (audit the audit — after every fix, check if the audit would have caught it, if not add a check). **Why:** Routing check (5.5A2) only verified directives went to the right place, not that the bot understood the user's intent. Monthly review didn't compare against decisions.log. No mechanism existed to improve the audit template itself based on findings.
- **2026-04-08:** Fixed memory.md ownership (root → openclaw). **Why:** Claude Code sessions run as root; files created/edited get root ownership. Bot runs as openclaw and can't write. Same issue as 2026-04-06 — root cause is Claude Code editing files in the repo. Fixed ownership on all new files created this session.
- **2026-04-08 (audit):** Applied 3 soul proposals. (1) Auto-sync Fitbit on sleep/weight/stats queries when data missing/stale — added to "How You Think" section. (2) Discretionary communication formatting (Grok-style) — replaced "Keep it concise" with flexible judgment in "How You Communicate". (3) Show previous session's performance when providing workout routines — added to "Core Rules". Rejected #102356 (superseded by #102628). **Why:** All user-directed during 04-08 morning session. **Connections:** soul.md, soul-proposals.jsonl (statuses updated).
- **2026-04-08 (audit):** Tightened said-vs-did warning regex in bot.py `_append_write_hallucination_notice()`. Removed overly broad patterns (`executing|done|complete`, `i can`) that matched past-tense descriptions of prior writes and future-tense suggestions. 5 false positives in today's session confused the user. **Why:** User asked "I don't understand your warning in the last sentence" — the banner fired when bot described already-completed actions or used phrases like "I can now correct". **Connections:** bot.py (action_phrases tuple).
- **2026-04-08 (audit):** Fixed fitbit_sync.py INSERT_ROWS → OVERWRITE. Same column drift bug fixed in bot.py on 2026-04-07 — fitbit_sync.py was missed. **Why:** fitbit_sync.py lives outside the repo (`/home/openclaw/fitbit_sync.py`) so it wasn't caught in the original sweep. **Connections:** fitbit_sync.py → Google Sheets (Body Metrics, Recovery, Nutrition tabs).
- **2026-04-08 (audit):** Cleared 15 phantom workout rows from Training Log. Bot triple-logged the 04-08 leg session (pyramid 340/360 + RPE finals + uniform 320). Kept only the final correct log (4 rows: LP 320x8x3, LC 100x10x3, LE 140x10x3, CC 8x10x3). **Why:** User sent workout data in stages, each got logged additively. Bot asked "clear if dupe?" but user was confused by the question. ~35k phantom volume removed.
