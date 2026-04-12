# J.A.R.V.I.S. — Architecture Document

Last updated: 2026-04-11

> **v2 rebuild in progress** — as of 2026-04-11, a full architectural rewrite is
> underway in `v2/`. The current system (bot.py + Google Sheets + gog + fitbit_sync)
> described below is still **live and untouched**. v2 is additive and reversible.
> Phase 0 (SQLite schema + importer) is complete. See `v2/README.md` for phase
> status and `decisions.log` entry `2026-04-11 | SQLite + deterministic router rebuild`
> for the full "why." This architecture doc continues to describe v1. When v2
> overtakes v1 (Phase 2+), this doc will be rewritten.

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
|-- morning-brief-ai.py             # 7am ET AI-generated Telegram brief (cron, openclaw)
|-- architecture.md                 # This file (system map for any AI/human)
|-- (procedures.md removed 2026-04-07 — consolidated into soul.md)
|-- (morning-brief.sh removed 2026-04-11 — superseded by morning-brief-ai.py)
|-- qa-check.sh                     # Daily integrity + procedure compliance check
|-- resolve.sh                      # CLI tool to mark QA issues as resolved
|-- resolved.jsonl                  # Log of resolved QA issues (checked before alerting)
|-- decisions.log                   # Append-only decision log (why-this-over-that)
|-- history-archive.md              # Tactical history pre-2026-04-11 (out of arch.md)
|-- daily-audit-template.md         # End-of-day Claude Code audit checklist (WHAT to check)
|-- audit-playbook.md               # Audit methodology + traps (HOW to audit) — read first
|-- claude-sessions/                # Claude Code session summaries (for retrieval after terminal drops)
|-- qa-hits.jsonl                   # QA check hit tracking (fed into monthly audit)
|-- monthly-audit.sh                # 9am 1st-of-month architecture audit
|-- auth-heartbeat.sh               # Hourly Google Sheets OAuth2 token heartbeat
|-- auto-commit.sh                  # Hourly git commit + push (uses .repo.lock vs bot writes)
|-- lifeos-bot.service              # systemd unit file (canonical copy of installed unit)
|-- requirements.txt                # Python deps: openai, python-telegram-bot
|-- openclaw.env.example            # Env var template (no real secrets)
|-- soul-proposals.jsonl             # Pending/processed soul.md change proposals
|-- review-soul-proposals.py        # Reviewer for soul proposals (NOT currently scheduled)
|-- .gitignore                      # Excludes logs/, uploads/, venv/
|-- memory/                         # AI-writable persistent state (markdown files)
|-- vendored/                       # Snapshots of files that live outside the repo (fitbit_sync.py)
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

**Schedule:** `0 7 * * *` ET (openclaw crontab — migrated from root 2026-04-11)
**Failure handling:** Exits non-zero on AI or Telegram failure; qa-check.sh Check 12 reads `morning-brief.log` next morning and re-alerts if last line isn't `Morning brief sent`.

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

Runs hourly via cron. Commits any changes in the repo (memory files the bot writes, manual edits, etc.) with message `auto: snapshot YYYY-MM-DD`. Does nothing if no changes.

**Schedule:** `0 * * * *` (openclaw crontab — migrated from root 2026-04-11)
**Lock:** `flock -n` on `/home/openclaw/lifeos/.repo.lock` so a future non-atomic writer can't race `git add -A`. Bot writes are append-only and already atomic via O_APPEND, so the lock is currently defensive only.
**Failure:** Push errors now exit non-zero (previously echoed silently). Cron mail catches them.
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

> **About the `openclaw` name:** The user account, env file, and home directory are still named `openclaw` because the box was originally provisioned for the OpenClaw Node.js system (replaced by `bot.py` on 2026-04-05). Renaming everything is purely cosmetic and would coordinate-touch user account, sudoers, systemd, cron, scripts, and the GitHub remote — high cost, no functional gain. Treat `openclaw` as "the lifeos service account."

> **External `.openclaw/` directory** (`/home/openclaw/.openclaw/`) — also a historical name, but it's load-bearing: `/usr/local/bin/gog` symlinks into `.openclaw/workspace/homebrew/bin/gog`, and `.openclaw/workspace/.config/gogcli/` holds the Google Sheets auth keyring. **Do not delete the homebrew or gogcli subdirectories.** All other OpenClaw cruft on the box (the npm package, openclaw.service, /etc/config/openclaw.json, and /opt/openclaw-*.sh wrappers) was deleted on 2026-04-11.

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

## Cron Jobs (openclaw crontab)

Migrated from root → openclaw on 2026-04-11. Running as openclaw means scripts touch
files as the same user that owns the repo, eliminating ownership drift to root.

| Schedule | Script | Purpose |
|----------|--------|---------|
| `0 7 * * *` ET | `morning-brief-ai.py` | Daily AI-generated Telegram morning brief |
| `0 * * * *` | `auto-commit.sh` | Hourly git snapshot (with `.repo.lock` flock) |
| `15 * * * *` | `auth-heartbeat.sh` | Hourly Google Sheets OAuth2 token heartbeat (alerts on first failure transition) |
| `30 8 * * *` ET | `qa-check.sh` | Daily integrity check (alerts only on failure) |
| `0 9 1 * *` ET | `monthly-audit.sh` | Monthly architecture audit report |

**Not currently scheduled:** `review-soul-proposals.py` (architecture previously
listed it as 8pm ET cron, but no entry exists in either crontab — possibly run
manually). Decision pending: schedule it or document as manual.

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

Every tool that writes data (log_workout, log_cardio, log_weight, log_nutrition, save_memory) reads the data back immediately. On success: returns `[VERIFIED]` in the result. On failure: returns `WRITE FAILED` with no success language — the model cannot claim the write succeeded because the tool result never says "Logged".

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
| 21 | File ownership drift | any tracked file (memory.md, soul.md, bot.py, architecture.md, etc.) not owned by openclaw — bot or cron can't write | Catches permission drift (expanded from memory-only on 2026-04-11) |
| 22 | Said-vs-did (log/save claims vs tool calls) | Bot claimed to log/save but no matching tool call exists | Catches action hallucinations |
| 23 | Exercise count mismatch | Bot discussed logging exercises but no log_workout calls found | Catches missed logging |
| 24 | Stale soul proposals | >5 pending/awaiting proposals in soul-proposals.jsonl | Catches review pipeline failures |
| 9a | Empty directories | Orphaned folders from old features | Orphan detection |
| ~~9b~~ | ~~Old openclaw service enabled~~ | (removed 2026-04-11 — migration complete, never fired) | — |
| 9c | Stale memory files (30d+) | Dead memory no one references | Orphan detection |
| 10 | Expected files exist | Core file accidentally deleted | Architecture drift |
| 11 | Git repo healthy | Repo broken or auto-commit failing | Backup integrity |
| 12 | Morning brief delivered | Cron ran but AI/Telegram failed | Silent delivery failure |
| 13 | Disk space (<85%) | Box filling up | Infrastructure health |
| 14 | RAM usage (<85%) | OOM risk | Infrastructure health |
| 15+18 | Fitbit + sleep freshness (2d) | (a) no Recovery rows = sync broken; (b) rows exist but sleep score blank = ring not worn. Single gog read serves both signals (merged 2026-04-11). | Data pipeline + completeness |
| 16 | Google Sheets auth | gog token expired | Data pipeline health |
| 17 | Caddy web server | Web endpoint down or unresponsive | Infrastructure health |
| ~~18~~ | (merged into 15+18 above on 2026-04-11) | — | — |
| 19 | Git remote reachable | Pushes silently failing, no backup | Backup integrity |

All hits are logged to `qa-hits.jsonl` for the monthly effectiveness audit.

**Why procedure checks:** The bot should follow specific tool call patterns (defined in `soul.md` under "Data Sources"). Example: when discussing body fat, it MUST read the Body Scans tab (DEXA data), NOT the Body Metrics tab (Renpho data). The QA catches when it takes shortcuts.

### Layer 4: Resolution tracking (zero tokens)

`resolved.jsonl` stores issues that have been fixed. The QA script checks this file before alerting — if an issue key is already resolved, it skips it.

**Why:** Without this, the QA keeps alerting on the same fixed problem forever. Wastes attention and causes alert fatigue. When a fix is applied, log it:

```bash
./resolve.sh "fitbit_sync_auth" "Fixed by running script directly instead of systemctl"
```

Each entry has: issue key, what fixed it, and the date. Match is **exact key only** (fixed 2026-04-11 — previous substring match meant resolving `no_training` silently auto-resolved every date-suffixed `no_training_2026-04-XX`). If the same issue reappears after a fix, date-specific keys won't match old resolutions, so it alerts again.

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

**Audit:** `daily-audit-template.md` Section 1 (Intent vs Action) catches misrouted directives — i.e. rules the user gave that the bot acknowledged but never persisted via `propose_soul_change` or `save_memory`.

**Connects to:**
- `bot.py` — `propose_soul_change` tool writes proposals
- `soul.md` — Claude Code applies approved proposals here
- `morning-brief-ai.py` — pending count shown in morning brief
- `daily-audit-template.md` — Section 1 catches missed routings
- `qa-check.sh` — Check 24 flags >5 stale proposals

**Files:**
- `soul-proposals.jsonl` — append-only proposal log with status tracking
- `review-soul-proposals.py` — standalone reviewer (currently manual, not cron'd — see "Cron Jobs" note)

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

**Landmark architectural decisions only.** Tactical fixes (regex tweaks, model swaps, individual bug fixes) live in `git log` and `decisions.log`. If an entry below stops describing how the system currently works, archive it to `history-archive.md` — don't accumulate cruft here.

- **2026-04-03:** OpenClaw (Node.js gateway + Docker sandbox) deployed.
- **2026-04-05:** Replaced OpenClaw with single Python file (`bot.py`). **Why:** OpenClaw's sandbox had a `ModuleNotFoundError` preventing all file writes; Docker/gateway abstraction was unnecessary complexity for a single-user bot.
- **2026-04-05:** Made all config env-driven (model, API key, base URL, chat ID, sheet ID). Swap providers without code changes.
- **2026-04-05:** Added read-after-write verification on all data writes + tool audit trail in conversation logs. **Why:** Catches silent write failures and claim-vs-action drift the moment they happen.
- **2026-04-05:** Added daily QA check (`qa-check.sh`) and resolution tracking (`resolved.jsonl`). **Why:** Catches data gaps, procedure violations, service outages at zero token cost; resolved.jsonl prevents alert fatigue.
- **2026-04-06:** Added PDF vision (`pdf2image` + poppler) and Google Drive browsing tools. **Why:** Bot can read DEXA scans, blood work, and Drive folders without re-uploads. Vision over text extraction for accuracy on formatted reports (integrity > efficiency).
- **2026-04-06:** System timezone set to America/Toronto. **Why:** `CRON_TZ` was being silently ignored by Vixie Cron — jobs were firing in UTC.
- **2026-04-06:** Added `decisions.log` — append-only record of "X over Y, because Z". **Why:** architecture.md captures *what changed*; decisions.log captures *why this over that*.
- **2026-04-07:** Consolidated `procedures.md` into `soul.md`. **Why:** Rules in multiple files drifted and contradicted each other. soul.md is now the single source of truth for bot behavior.
- **2026-04-08:** Added soul proposal pipeline (`propose_soul_change` tool → `soul-proposals.jsonl` → Claude Code review → soul.md). **Why:** "Tell Claude Code to update soul.md" pattern lost directives across sessions. Pipeline captures immediately and routes through review.
- **2026-04-08:** Trimmed soul.md from 116 → ~50 LOC. **Why:** Heavy constraints were consuming model cognitive budget; user observed model performed better with minimal prompt + code-level monitoring than with long instructions. Monitoring stayed in bot.py (untouched).
- **2026-04-09:** Switched all logging tools from `gog sheets append` to targeted `gog sheets update` via `_find_next_row`. **Why:** Append modes (INSERT_ROWS, OVERWRITE) caused column drift when blank rows existed in the sheet. Targeted updates bypass that class of bug entirely.
- **2026-04-11 (sleep score real fix):** The 2026-04-08 "fix" for sleep score was a no-op — Fitbit's `/1.2/user/-/sleep/date/.json` endpoint does NOT return a `score` field at all. Column B "Sleep Score" had been efficiency the whole time. Fixed properly: renamed col B → "Efficiency %", added new col J "Sleep Score (computed)" populated by a 0-100 proxy formula (50% duration / 25% efficiency / 25% restoration). Validated against the user's previously-observed Fitbit app score of 76 on 4/08 — formula gives 79 (within 3 points). Backfilled 24 historical rows. Also fixed `pull_sleep` to sum across ALL sleep sessions (was main-session-only — naps were ignored). Sleep Hours column C now shows total daily sleep including naps. `fitbit_sync.py` snapshotted to `vendored/fitbit_sync.py` for version control. Cleared one orphan corrupt row (35) from old INSERT_ROWS column-drift bug. soul.md Recovery columns documented.
- **2026-04-11 (auth heartbeat + OAuth2 reauth):** Google Sheets OAuth2 token was revoked (cause unknown — possibly external Google action). Reauth performed via the curl-the-failed-callback-URL trick (gog has no OOB flow). Added `auth-heartbeat.sh` running hourly via cron — closes the 24-hour blind window where qa-check Check 16 wouldn't catch a mid-day token revocation. Heartbeat uses a state file so it only alerts on transitions (good→bad and bad→good), not every hour. Reauth procedure documented in `audit-playbook.md`.
- **2026-04-11 (OpenClaw cruft cleanup):** Removed leftover OpenClaw installation from outside the lifeos repo. Deleted: `/usr/lib/node_modules/openclaw` (1.4 GB npm package + 13 extensions), `/etc/systemd/system/openclaw.service` (orphan, was disabled+inactive), `/etc/config/openclaw.json` (Docker sandbox config), and 6 `/opt/openclaw-*.sh` wrapper scripts. **Kept** (load-bearing): `/opt/openclaw.env` (active env file), `~/.openclaw/workspace/homebrew/` (gog binary), `~/.openclaw/workspace/.config/gogcli/` (Google auth keyring). **1.3 GB freed.**
- **2026-04-11 (lean sweep):** Architecture audit and consolidation pass. **Cron migrated root → openclaw** (eliminated ownership-drift class at the source). **Model reverted** GPT-4.1-mini → Grok 4.1 fast (integrity > efficiency — Category 2 hallucinations spiked after 04-08 swap). **resolved.jsonl substring bug fixed** (was silently auto-resolving date-suffixed keys). **auto-commit/morning-brief silent failures made loud.** **bot.py log_* functions deduplicated** into one `_write_and_verify` helper. **qa-check.sh hardened** (Check 9b removed, Check 21 expanded, Checks 15+18 merged, integer arithmetic pattern fixed). **daily-audit-template.md rewritten** 252 → 61 LOC (kept only manual-only sections). **Routine moved soul.md → memory.md** (one source of truth for facts about user). **History archived** to `history-archive.md` to stop arch.md growing forever. **SSH deploy key set up** for openclaw → GitHub. See `decisions.log` 2026-04-11 entries for full reasoning. Tactical details in commit history.

**Tactical history before 2026-04-11:** see `history-archive.md`.
