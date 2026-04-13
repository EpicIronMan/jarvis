# LifeOS v2 — SQLite + deterministic-router rebuild (LIVE)

**v2 is now the running system.** bot.py routes through v2 for all CRUD.
Claude Sonnet handles coaching/analysis. SQLite is source of truth.
Google Sheets is a one-way read-only mirror.

## Phase status

| Phase | Goal | Status |
|-------|------|--------|
| 0 | SQLite schema + one-shot sheet importer + verified row parity | **done 2026-04-11** |
| 1 | Deterministic router + query handlers + read-path CLI | **done 2026-04-11** |
| 1.5 | Expand coverage + LLM fallback + bug fixes + 124 tests | **done 2026-04-12** |
| 2 | Write path + bot.py cutover + fitbit ingest + sheet export + morning brief | **done 2026-04-12** |
| 3 | Sonnet swap + cleanup + qa-check rewrite + soul.md + architecture.md | **done 2026-04-12** |
| 4 | Proactive coaching triggers (no-training-2d, protein, weight direction) | **done 2026-04-12** |

Rollback: `cp bot.py.v1.backup bot.py && systemctl restart lifeos-bot`

## Files

- `schema.sql` — the full DB schema. Single source of truth for table shape.
  9 tables + 3 views + STRICT mode for type enforcement. **This file IS the
  architecture doc for the data layer.** If you want to know what v2 stores,
  read this.
- `import_from_sheets.py` — one-shot importer from the live Google Sheet via
  `gog`. Fail-loud on missing required fields. Strict ISO-date validation
  (skips header + comment rows). Re-runnable (drops and recreates lifeos.db).
- `lifeos.db` — the SQLite file. **Gitignored** (binary). Backups and a
  daily `.dump` will live alongside it once Phase 2 ships.
- `handlers/dates.py` — deterministic date resolution in America/Toronto.
  Parses "today", "yesterday", "N days ago", weekday names, ISO strings,
  and range tokens ("last 7 days", "this week", "this month").
- `handlers/query.py` — SELECT helpers per table. Structured-dict returns.
  Null-aware averages for range summaries. Fuzzy exercise matching.
- `handlers/classify.py` — LLM fallback classifier. Router misses go to
  Claude Haiku with a strict JSON contract. Hallucinated intents rejected.
- `router.py` — deterministic intent regex matcher. 16 intents, ~35 patterns.
- `lifeos_cli.py` — read-path harness (router → handler → JSON output).
  Supports `--no-llm` for router-only mode.
- `tests/` — 124 pytest tests. Router, dates, query helpers, bug regressions.
- `README.md` — this file.

## How to re-run the importer (Phase 0 only)

```bash
sudo -n -u openclaw bash -c '
  . /opt/openclaw.env
  export GOG_KEYRING_PASSWORD GOG_ACCOUNT SHEET_ID
  cd /home/openclaw/lifeos/v2
  python3 import_from_sheets.py
'
```

Importer is idempotent: it drops and recreates `lifeos.db` each run.

## Current Phase 0 row counts (verified against live sheet 2026-04-11)

| Table         | Rows | Notes |
|---------------|------|-------|
| body_metrics  | 30   | 31 sheet rows − 1 comment row |
| body_scan     | 1    | DEXA 2026-04-02 |
| nutrition     | 35   | 36 sheet rows − 1 comment row |
| workout       | 28   | full Training Log |
| cardio        | 3    | full Cardio tab |
| recovery      | 38   | 40 sheet rows − 1 comment − 1 empty |
| **total**     | **135** | |

Parity spot-checks: `body_metrics`, `nutrition`, `recovery` rows for
2026-04-11 compared cell-by-cell against the live sheet. Clean.

## Known latent bugs carried over from v1 (NOT fixed in v2 yet)

- `fitbit_sync.py` partial-update overwrite: when Fitbit API returns no value
  for steps/active_minutes/resting_hr on a re-sync, the script writes empty
  strings over previously-good data. Observed on 2026-04-11 Recovery row
  (steps went from 564 → blank between 11:39 and 16:00 ET syncs). **Fix in
  Phase 2** when the new deterministic `ingest_fitbit.py` handler is written
  — partial updates must preserve existing non-null values.
