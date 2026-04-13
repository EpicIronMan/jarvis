# LifeOS v2 — Staging area for the SQLite + deterministic-router rebuild

This directory holds the in-progress v2 rewrite. **The running system at
`/home/openclaw/lifeos/` (bot.py, morning-brief-ai.py, qa-check.sh, Google
Sheets as source of truth) is untouched** — v2 is additive.

See `decisions.log` entry `2026-04-11 | SQLite + deterministic router rebuild`
for the full rationale. Short version: every "fix" since 2026-04-08 has been
a patch for model-behavior failures (hallucinations, said_not_did,
said_failed_not_tried, bf_wrong_source, wrong-date answers, avoidance pivots).
Root cause: we placed a probabilistic component in charge of deterministic
CRUD work. v2 inverts that — scripts do CRUD and date math and retries; the
model writes coaching prose, parses DEXA scans, and handles on-demand analysis.

## Phase status

| Phase | Goal | Status |
|-------|------|--------|
| 0 | SQLite schema + one-shot sheet importer + verified row parity | **done 2026-04-11** |
| 1 | Deterministic router + query handlers + read-path CLI | **done 2026-04-11** |
| 1.5 | Expand coverage + LLM fallback + bug fixes + tests | **done 2026-04-12** |
| 2 | Write path on SQLite + one-way DB→read-only-sheet export | pending |
| 3 | Cleanup (delete gog, .openclaw, auth-heartbeat, vendored/) + Claude Sonnet model swap | pending |
| 4 | Trim qa-check.sh + harden based on real v2 event log | pending |

v2 is fully reversible until Phase 2 begins. `rm -rf v2/` undoes everything
through Phase 1.

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
