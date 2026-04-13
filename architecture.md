# J.A.R.V.I.S. — Architecture Document (v2)

Last updated: 2026-04-13

## Maintenance Rule

**Any AI or human that changes any file in this repo MUST update this file in the same session.**

## Design Principle

**Musk's Algorithm applies to every change:** Question the requirement → Delete → Simplify → Accelerate → Automate. Don't optimize what shouldn't exist.

Deterministic Python handles CRUD writes, timezone-sensitive date math, and schema enforcement. The LLM handles all natural language comprehension — including date ranges, ambiguous queries, and intent classification. Don't put deterministic code in front of what the LLM already understands.

LLM scope:
1. Coaching prose and analysis
2. DEXA PDF data extraction (vision)
3. All range/trend queries (natural language → tool calls)
4. Classifying ambiguous queries that miss the regex router

This architecture evolved from the 2026-04-11 rebuild (deterministic-first) refined by 2026-04-13 lesson: regex range routing intercepted and broke natural language the LLM handles natively. Range routes deleted; intent names preserved for classifier.

## Data Flow

```
User (Telegram)
  ↓
bot.py receives message
  ↓
v2/router.py (regex intent matcher, ~35 patterns, 16+ intents)
  ↓ match?
  YES → v2/handlers/query.py or log.py → SQLite → formatted response → Telegram
  NO  → v2/handlers/classify.py (Claude Haiku, picks from known intents)
       ↓ classified?
       YES → same handler path
       NO  → Claude Sonnet full conversation (coaching/analysis)
            → may call tools: query_data, log_*, save_memory, sync_fitbit
```

## Source of Truth

**SQLite** (`v2/lifeos.db`) is the single source of truth for all data. Google Sheets is a one-way read-only mirror, updated by `v2/export_to_sheet.py`.

## Components

### Core Bot
- **`bot.py`** — Telegram bot. Routes messages through v2 router. CRUD handled deterministically. Coaching via Claude Sonnet (Anthropic SDK). Handles PDF/photo uploads with vision.
- **`soul.md`** — System prompt for coaching mode. Contains user stats, core rules, data source rules. Reloaded on every LLM call.

### v2/ — Deterministic Engine
- **`v2/router.py`** — Regex intent router. Handles single-date queries, bare keywords, write shorthand, and commands. Range queries are NOT routed here — the LLM handles them. Never resolves dates (that's dates.py's job).
- **`v2/handlers/dates.py`** — All date resolution. America/Toronto timezone. The model never decides what "yesterday" means.
- **`v2/handlers/query.py`** — Read-only SELECT helpers. Returns structured dicts. Null-aware averages, fuzzy exercise matching, stats fallback.
- **`v2/handlers/log.py`** — Write handlers (INSERT/UPDATE). All writes go through here. Audit events logged automatically.
- **`v2/handlers/classify.py`** — LLM fallback for router misses. Claude Haiku picks from known intent set. Hallucinated intents rejected.
- **`v2/handlers/dexa.py`** — DEXA PDF → vision → body_scan table. Narrow LLM scope.
- **`v2/schema.sql`** — 9 STRICT tables + 3 views. This IS the data layer architecture doc.
- **`v2/lifeos.db`** — SQLite file. Gitignored (binary). Backed up hourly.
- **`v2/lifeos.sql`** — Text dump for git (diff-friendly history).
- **`v2/lifeos_cli.py`** — CLI harness for testing queries.

### Data Pipeline
- **`v2/ingest_fitbit.py`** — Fitbit API → SQLite. Replaces v1 fitbit_sync.py. Preserves non-null values on partial updates (fixes the overwrite bug). Runs via systemd timer.
- **`v2/export_to_sheet.py`** — SQLite → Google Sheet (one-way, via gog). Cron every 5 min.
- **`v2/morning_brief.py`** — Daily 7am ET brief from SQLite. Assembles structured data, calls Claude for prose, sends to Telegram.

### Infrastructure
- **`v2/backup.sh`** — Hourly SQLite backup with 48h/30d/12m retention ladder.
- **`auto-commit.sh`** — Hourly git commit (includes lifeos.sql dump).
- **`qa-check.sh`** — Daily integrity checks: SQLite health, event log, backup freshness, service status.

### Files Removed (Phase 3)
- `fitbit_sync.py` (at /home/openclaw/) — replaced by v2/ingest_fitbit.py
- `auth-heartbeat.sh` — no longer needed (SQLite doesn't require OAuth)
- `vendored/` — no longer needed
- Google Sheets tools in bot.py — replaced by SQLite handlers

### Kept But Deprecated
- `gog` CLI — still used by export_to_sheet.py. Will be replaced by google-api-python-client.
- `/home/openclaw/.openclaw/` — gog config. Keep until gog is replaced.

## Crontab (openclaw user)

| Schedule | Script | Purpose |
|----------|--------|---------|
| 0 7 * * * | v2/morning_brief.py | Daily morning brief |
| 0 * * * * | auto-commit.sh | Hourly git commit |
| 30 8 * * * | qa-check.sh | Daily QA checks |
| */5 * * * * | v2/export_to_sheet.py | SQLite → Sheet mirror |
| 0 * * * * | v2/backup.sh | Hourly SQLite backup |

Fitbit sync runs via `fitbit-sync.timer` systemd timer (3x/day → v2/ingest_fitbit.py).

## Environment Variables

All from `/opt/openclaw.env`:
- `TELEGRAM_BOT_TOKEN`, `CHAT_ID` — Telegram
- `ANTHROPIC_API_KEY` — Claude API (bot + classifier + morning brief + DEXA)
- `SHEET_ID`, `GOG_ACCOUNT`, `GOG_PATH`, `GOG_KEYRING_PASSWORD` — Sheet export
- `LIFEOS_DIR` — repo path (default: /home/openclaw/lifeos)
- `AGENT_NAME`, `AGENT_EMOJI` — bot identity

## Tests

124+ pytest tests in `v2/tests/`. Run: `cd v2 && python3 -m pytest tests/ -v`
