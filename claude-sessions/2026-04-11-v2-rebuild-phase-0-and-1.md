# v2 Rebuild — Phase 0 + Phase 1 (April 11, 2026)

## What this session did

The user green-lit a full first-principles rebuild of LifeOS after today's
audit found 4 distinct failures in a single conversation — all model-behavior
root-caused (1 hallucination, 1 wrong-date-arithmetic, 1 avoidance pivot,
1 context pattern-matching bias). Prior to this session, every "fix" since
2026-04-08 had been a patch for model misbehavior: model swaps, qa-check
adds, etc. Root cause wasn't "the model is bad" — it was that a probabilistic
component was placed in charge of CRUD + date math + tool dispatch + retry
logic + action recall.

v2 inverts the hierarchy: deterministic Python for all CRUD/retry/date work,
model narrowed to coaching prose + DEXA vision + genuinely ambiguous parsing.
SQLite replaces Google Sheets as source of truth (eliminates 7-day OAuth tax,
kills gog, kills dual-config drift). Sheets stays as a one-way read-only view
in Phase 2.

Phased migration: 0 schema+import, 1 read path, 2 write path + sheet export,
3 cleanup + Sonnet model swap + tests, 4 trim.

**Phases 0 and 1 were both completed this session. v1 is still live and
untouched through the end of Phase 1.**

## Phase 0 commit: `c55b739`

- `v2/schema.sql` — 9 STRICT tables (body_metrics, body_scan, nutrition,
  workout, cardio, recovery, routine versioned, user_facts, events audit)
  + 3 convenience views. WAL mode, indexes on date columns.
- `v2/import_from_sheets.py` — gog-fed one-shot importer with strict
  ISO-date validation (rejects header + comment rows), fail-loud on missing
  required workout fields, idempotent.
- `v2/lifeos.db` — gitignored. **135 rows imported**: body_metrics 30,
  body_scan 1, nutrition 35, workout 28, cardio 3, recovery 38.
- `v2/README.md` — phase status, row counts, known v1 carry-over bugs.
- `.gitignore` — excludes `v2/lifeos.db` + WAL/SHM + backups.
- `architecture.md` — v2 pointer added at top.
- `decisions.log` — big architectural entry with options + choice + why.

**Parity spot-check:** 2026-04-11 rows in body_metrics, nutrition, and
recovery compared cell-by-cell against live sheet. Clean.

**One import bug caught and fixed mid-session:** first pass allowed comment
rows ("← One row per day…" in row 2 of Body Metrics / Nutrition / Recovery)
through as garbage data. Fix: strict `ISO_DATE_RE` date validation in the
importer. Re-run clean.

**Latent v1 bug NOT fixed (noted for Phase 2):** `fitbit_sync.py`
partial-update overwrite. The 2026-04-11 Recovery row showed `steps=564`
at the 11:39 ET sync and `steps=""` (blank) after the 16:00 ET sync —
the re-upsert wrote empty strings over real data. Fix target: the new
`ingest_fitbit.py` handler in Phase 2 must preserve existing non-null
values on partial updates.

## Phase 1 commit: `64ef9af`

- `v2/handlers/dates.py` — date resolution in America/Toronto. Parses
  "today", "yesterday", "N days ago", weekday names, ISO strings, and
  range tokens ("last 7 days", "last/past week", "this week", "last/past
  month", "this month"). **The model no longer decides what "yesterday"
  means.**
- `v2/handlers/query.py` — SELECT helpers per table. Structured-dict
  returns ready for formatting or prose generation. Key functions:
  `latest_weight`, `latest_body_scan`, `nutrition_for_date`,
  `recovery_for_date`, `training_on_date`, `last_training_session`,
  `last_session_of_exercise`, `stats_snapshot`.
- `v2/router.py` — deterministic intent regex matcher. 10 intents:
  stats, weight_latest, weight_for, nutrition_for, training_for,
  training_latest, recovery_for, body_scan_latest, routine_today,
  last_exercise. **Router extracts date tokens but never resolves them
  — that's dates.py's job.**
- `v2/lifeos_cli.py` — smoke-test harness for the read path. Takes a
  Telegram-style message, routes + dispatches + prints JSON. Not wired
  to Telegram. Exit codes: 0 ok / 1 handler err / 2 unroutable / 3 usage.

**Smoke tests (16 queries, all pass against lifeos.db):**
- "what are my stats" → full omnibus snapshot
- "weight today" / "weight yesterday" → correct dates (the 07:28 ET
  gpt-4.1-mini failure is now structurally impossible)
- "nutrition today" / "nutrition yesterday" → correct
- "last workout" → 2026-04-11 session (Seated Leg Press + Captain Chair)
- "training 2026-04-09" → full 6-exercise back session
- "latest dexa" → 2026-04-02 DEXA row
- "sleep last night" → 2026-04-10 recovery (honestly reports NULL sleep_hours
  inherited from the v1 fitbit_sync partial-update bug)
- "steps today" → 2026-04-11 recovery
- "weight 2026-04-09" → ISO date passes through
- "last leg press" → 2026-04-08 session (Leg Press)
- "last seated leg press" → 2026-04-11 session (Seated Leg Press)
  **This distinguishes between the two exercise names that today's v1 bot
  conflated at 17:31 ET when asked to rename historical rows. SQL handles
  it, model never gets a chance to pivot.**
- "my routine" / "what should I do today" → polite "routine not seeded,
  Phase 2 will seed" message. No fabrication, no guessing.

## State of v1 at end of session

**Completely untouched.** bot.py, morning-brief-ai.py, qa-check.sh,
fitbit_sync.py, crontab, systemd unit, gog, sheets, OAuth — all unchanged.
If the user messages the Telegram bot right now it responds exactly as
it did at the start of the session.

## Decisions made this session (tracked in decisions.log)

1. SQLite replaces Sheets as source of truth — committed.
2. Deterministic router replaces LLM orchestration for CRUD — committed.
3. Phased migration (0→1→2→3→4) keeps v1 live through Phase 1 — committed.
4. Routine versioned SQLite table (not JSON file) — implemented in schema.
5. One-way DB→read-only-sheet export (not "fully cut the cord") — Phase 2.
6. Claude Sonnet model swap at Phase 3, not earlier (hold model constant
   during architecture migration) — Phase 3.
7. `.gitignore` the binary `lifeos.db`, commit daily `.dump` text — Phase 2.
8. Keep LLM-vision for DEXA PDF parsing (narrow scope, rare use) — Phase 2.
9. Telegram router intents + SSH escape hatch for manual edits; no web UI
   day one — Phase 2.
10. Hourly backup snapshots with 48h/30d/12m retention ladder — Phase 2.
11. Start with exactly 3 proactive coaching triggers (no framework) —
    Phase 2 or 3.
12. **openclaw rename deferred to Phase 3 or later** — cosmetic only,
    high coordination cost, defer the call until the cleanup phase.

## What's still open (Phase 2 and beyond)

### Phase 2 (next session, requires explicit go-ahead because it modifies v1)

- Write `v2/handlers/log.py` with log_weight, log_workout, log_nutrition,
  log_cardio, log_body_scan — INSERT path.
- Add router intents for write shorthand ("log weight 172 renpho",
  "3x10 320 seated leg press", "edit weight 2026-04-10 to 171.5").
- Add `rename_exercise` router intent + handler (the thing that was silently
  dropped at 17:31 today because v1 had no tool for it — one SQL UPDATE).
- Write `v2/export_to_sheet.py` — one-way SQLite → read-only Google Sheet
  push. Runs on cron or on-write trigger. Uses gog ONE MORE TIME for the
  push, then Phase 3 replaces it with google-api-python-client.
- Write `v2/ingest_fitbit.py` — replaces v1 `fitbit_sync.py`. Writes to
  SQLite directly, preserves existing non-null values on partial updates
  (fixes the 2026-04-11 Recovery row bug).
- Write `v2/handlers/dexa.py` — pdf2image + Claude vision, narrow scope,
  writes body_scan row.
- Write `v2/morning_brief.py` — deterministic 7am ET brief from SQLite.
- Seed the `routine` table with current bro split (user needs to confirm
  the day→session mapping — v2 shouldn't guess).
- Seed the `user_facts` table with height, birth_date, goal_weight,
  goal_bf_pct (move from memory/ markdown to SQL).
- **Modify bot.py** to route through v2 router for both reads and writes.
  This is the v1 cutover point — reversible only by `git revert`.
- Write `v2/auto_commit_dump.sh` — replaces auto-commit.sh with a
  `sqlite3 lifeos.db .dump > lifeos.sql` step before add/commit.
- Hourly backup cron (`cp lifeos.db backups/lifeos-$(date …).db`) with
  the 48h/30d/12m retention ladder.

### Phase 3 — cleanup + Sonnet swap + tests

- Delete `/home/openclaw/.openclaw/` (gog binary + keyring).
- Delete `/usr/local/bin/gog` symlink.
- Delete `auth-heartbeat.sh`, `auth-heartbeat.log`.
- Delete `v2/export_to_sheet.py` gog dependency, replace with
  google-api-python-client.
- Delete `vendored/fitbit_sync.py` snapshot dir.
- Trim `qa-check.sh`: delete Checks 8 (bf_wrong_source), 16 (sheets auth),
  22 (said_not_did), 25 (said_failed_not_tried) — their bug classes can't
  exist anymore. Keep 1, 10, 11, 13, 14 (infrastructure health).
- Swap bot to Claude Sonnet via env vars (integrity argument: better
  instruction-following on structured-output contracts).
- Add `v2/tests/` — pytest against in-memory SQLite. Every handler.
- Rewrite `architecture.md` from scratch to describe v2.
- Rewrite `soul.md` as coaching-tone only (no orchestration rules).
- **Reconsider openclaw rename** — contained scope within broader cleanup.

### Phase 4 — trim and harden

- Watch event log for a week, delete checks that never fire, harden
  anything the event log reveals as model-behavior leakage.
- Add proactive triggers (no-training-2d, protein-below-target-3d,
  weight-wrong-direction-7d).

## For the next session

If the user says "go Phase 2":
1. Read this session log.
2. Check `git log --oneline -5` — should see `64ef9af` (Phase 1) and
   `c55b739` (Phase 0) at the top.
3. Confirm `lifeos.db` still exists at `/home/openclaw/lifeos/v2/lifeos.db`
   and has 135 rows. If not, re-run `import_from_sheets.py`.
4. Run `python3 /home/openclaw/lifeos/v2/lifeos_cli.py "what are my stats"`
   to verify the read path still works.
5. Ask the user about the routine seeding (day-of-week → session-type →
   exercise list) before seeding the `routine` table — don't guess from
   the training log.
6. Ask the user about the sheet-export cadence (on-write trigger vs
   every-30-seconds cron vs hourly).
7. Start Phase 2 tasks from the "Phase 2" list above.

## Gotchas encountered this session

- **git config** — openclaw user has no `.gitconfig`. auto-commit.sh uses
  per-invocation `-c user.email="jarvis@lifeos" -c user.name="J.A.R.V.I.S."`
  flags. Copy that pattern; don't run `git config --global`.
- **gog keyring** — `sudo -n -u openclaw bash -c ...` scrubs the
  environment. Always `export GOG_KEYRING_PASSWORD GOG_ACCOUNT SHEET_ID`
  after sourcing `/opt/openclaw.env` inside the sub-shell.
- **gog JSON output** — use `-j --render UNFORMATTED_VALUE` for scripting.
  Numbers come back as strings even with UNFORMATTED — coerce in code.
  Trailing empty cells are omitted from JSON arrays — pad to column count.
- **Sheet row ordering is not chronological.** `Nutrition!A3:I3` is NOT
  yesterday's row; row numbers are assigned by insertion order, not date.
  Always query by date-value, not row position.
- **Comment rows** — Body Metrics, Nutrition, and Recovery all have a
  human-readable comment row (row 2) starting with "← One row per day…".
  Strict ISO-date validation in the importer handles it. Body Scans,
  Training Log, and Cardio do NOT have this pattern.
- **Chown after every session as root.** Anything Claude Code writes is
  root-owned by default. `chown -R openclaw:openclaw /home/openclaw/lifeos`
  before ending the session.
