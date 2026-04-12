# v2 Rebuild — Session 1 state (April 11, 2026, ~21:15 ET end)

> **Status:** Phases 0 and 1 committed and pushed to GitHub. v1 bot is
> still live and healthy. Session paused between Phase 1 and Phase 2,
> **waiting on user decisions** about Hevy adoption + historical-data strategy
> before Phase 2 can start. Next session resumes here.

---

## ⚡ START HERE — resume checklist for the next session

Read the whole file, but these are the immediate actions in order:

1. **Verify state is still as described:**
   ```bash
   cd /home/openclaw/lifeos
   git log --oneline -5
   # Should see (top-to-bottom):
   #   7c7e256 auto: snapshot 2026-04-11   (the auto-commit that pushed this file)
   #   64ef9af v2 Phase 1: deterministic router + query handlers + read-path CLI
   #   c55b739 v2 Phase 0: SQLite schema + one-shot sheet importer
   # ... and older auto: snapshots below
   systemctl is-active lifeos-bot         # should say 'active'
   ls /home/openclaw/lifeos/v2/lifeos.db  # should exist
   ```
   If any of these are wrong, something regressed since 2026-04-11 21:15 ET and you need to diagnose before proceeding.

2. **Re-run the smoke test to confirm v2 read path still works:**
   ```bash
   sudo -n -u openclaw python3 /home/openclaw/lifeos/v2/lifeos_cli.py "what are my stats"
   ```
   Should return a JSON dict with `latest_weight`, `latest_body_scan`, etc. If it errors or hangs, read the full session context below before fixing.

3. **Ask the user for the 3 decisions listed in "OPEN QUESTIONS" below.** These are blockers for Phase 2. Don't start Phase 2 work until they answer — the Phase 2 scope changes meaningfully depending on whether Hevy is in or out.

4. **Once user answers:** go to the "NEXT PHASE PLAN" section below for the revised Phase 1.5 / Phase 2 work list.

---

## OPEN QUESTIONS — these block Phase 2

### Q1. Hevy app — adopt it as the primary workout logging input?

I researched it mid-session (sources at bottom of file). Short version:
- Hevy has a real, public, documented REST API at `api.hevyapp.com/docs` (Swagger).
- Returns workout sessions with sets/reps/weight/rest times natively — maps directly to the v2 `workout` table.
- API key auth, **not OAuth** — no 7-day expiry drama, no refresh-token revocation.
- **Requires Hevy Pro subscription** (~$5–8/month, didn't verify current pricing).
- Community libraries exist (hevy-mcp, Hevy-Coach) for reference implementations.

If yes, Phase 2 shape changes: drop the heavy Telegram workout-shorthand parser, add `v2/handlers/ingest_hevy.py` cron. Telegram becomes query/edit layer only. The `rename_exercise` tool I flagged today becomes unnecessary because Hevy maintains canonical exercise names.

If no, Phase 2 stays as originally planned: deterministic shorthand parser in the router, Telegram as primary log input.

**User needs to answer:**
  - Q1a: Do you already use Hevy, or would this be new adoption?
  - Q1b: Are you OK paying for Hevy Pro?
  - Q1c: If yes to Hevy — what to do with the 28 existing workout rows in v2/lifeos.db?
    - **A** Pull Hevy history back via API, merge+dedupe with existing rows
    - **B** Keep the 28 rows as-is, cutover to Hevy from a chosen date forward (simplest; my recommendation)
    - **C** Log in both Hevy + Telegram for a week in parallel, reconcile, then cutover

### Q2. Routine table seeding — what's your actual weekly split?

The `routine` table is empty. Until it's seeded, the `routine_today` intent returns a polite "not seeded yet" message. Don't guess from the training log — user must provide:
- Monday → (session type, exercise list or Hevy routine ID)
- Tuesday → …
- through Sunday, including REST days

If the user picks Hevy in Q1, this might move — Hevy has its own routine/template system and we could pull the routine via API instead of storing it in SQLite. Decide *after* Q1.

### Q3. Sheet export cadence (one-way SQLite → read-only Google Sheet)

- **A** On-write trigger (log handler pushes after INSERT) — tightest latency, slightly more code
- **B** Every 30 seconds cron — simpler, always pushes even if nothing changed
- **My recommendation** (still valid): **A + safety-net 5-minute cron** as belt-and-suspenders

### Q4. Sonnet swap timing

Originally Phase 3, I briefly floated Phase 2. **I still recommend Phase 3** — hold model constant during architecture migration so any behavior change is attributable to architecture not model. User hasn't confirmed or overridden. Default to Phase 3 unless they say otherwise.

---

## WHERE WE ARE RIGHT NOW

### What's committed and pushed

| Commit | What | Status |
|---|---|---|
| `c55b739` | v2 Phase 0: SQLite schema + one-shot sheet importer | on GitHub |
| `64ef9af` | v2 Phase 1: deterministic router + query handlers + read-path CLI | on GitHub |
| `7c7e256` | auto-commit snapshot including this session log | on GitHub |

### v1 state (as of 2026-04-11 21:15 ET)

**Fully healthy, fully untouched.** Verified via health-check battery at end of session:
- `lifeos-bot` service active, running since 12:15 EDT, polling Telegram normally
- openclaw crontab intact — morning brief, auto-commit, qa-check, monthly audit, auth-heartbeat all scheduled
- `auth-heartbeat.log` showing consecutive `ok`
- `fitbit-sync.timer` active, next trigger Sun 2026-04-12 02:00 EDT
- No root-owned files anywhere in the repo
- The v2/ work did not touch a single byte of v1

**One minor warning noted, non-blocking:** `qa-check.sh` has bash integer errors on lines 51 and 99 — the classic `grep -c … || echo 0` → `"0\n0"` trap from the audit-playbook. Script-level warnings, not data corruption. Fix during Phase 3 qa-check rewrite.

### v2 state (as of 2026-04-11 21:15 ET)

- `v2/schema.sql` — 9 STRICT tables + 3 views. Validated.
- `v2/import_from_sheets.py` — gog-fed importer with strict ISO-date validation. Idempotent.
- `v2/lifeos.db` — **135 rows imported** across 6 tables:
  | table | rows |
  |---|---|
  | body_metrics | 30 |
  | body_scan | 1 |
  | nutrition | 35 |
  | workout | 28 |
  | cardio | 3 |
  | recovery | 38 |
- `v2/router.py` — 10 regex intents
- `v2/handlers/dates.py` — ET date resolution (today/yesterday/N days ago/weekdays/ranges)
- `v2/handlers/query.py` — SELECT helpers per table
- `v2/lifeos_cli.py` — read-path smoke-test harness
- `v2/README.md` — phase status tracker
- `v2/handlers/__init__.py` — empty package marker
- Phase 0 parity spot-check passed on 2026-04-11 rows across body_metrics / nutrition / recovery.
- Phase 1 smoke tests: 16 queries all correct, including the exact failures from today's audit.

### Tables empty on purpose (Phase 2 will seed)

- `routine` — blocked by Q2
- `user_facts` — will hold height, birth_date, goal_weight, goal_bf_pct (currently in memory/ markdown)
- `events` — audit substrate. Nothing writes to it yet. Phase 2 handlers will.

---

## Self-audit on Phase 1 (honest end-of-session assessment)

I was asked "does everything look good?" and the honest answer is **no, Phase 1 is functional but sparse.** Issues ranked:

**Blocking for Phase 2:**

1. **Router coverage is thin — 10 intents.** v1's LLM handled anything. v2 only handles 10 specific phrasings. Common things miss:
   - "how did I sleep" — unroutable
   - "what's my protein today" — unroutable
   - "training 3 days ago" — unroutable (date-bearing patterns only accept `today|yesterday|\d{4}-\d{2}-\d{2}`)
   - "last 7 days weight" — no range intents exist at all
   - "weight monday" — weekday name not in weight_for pattern
   - "last bench" — exact-match only, won't match "Bench Press"
2. **No LLM fallback for router misses.** Phase 1 plan said "fall through to LLM classifier" — I didn't build it. Right now router miss returns None and CLI prints "no pattern matched". In Phase 2 when bot.py uses this, the LLM fallback is mandatory.
3. **`dates.resolve_range` exists but nothing uses it.** The resolver supports "last 7 days" / "this week" / "last month" but no router intent exposes it.
4. **`last_exercise` exact-match is fragile.** "last bench" gives empty results because rows say "Bench Press". Needs LIKE fuzzy match or documented strict rule.

**Real bugs (fix when touched):**

5. **`nutrition_range_summary` averages NULL as 0.** A week with 3 missed days would report avg calories ~30% lower than reality. Should skip nulls or require `n = days with non-null calories`.
6. **`bf_wrong_source` is not actually fixed — it's been rebranded as "convention".** Nothing in v2 code *prevents* a handler from pulling `body_metrics.body_fat_pct` (Renpho bioimpedance) instead of `body_scan.total_bf_pct` (DEXA). I added schema comments. Comments aren't enforcement. Consider a view or a query-layer rule.
7. **`events` audit table is inert.** Nothing writes to it yet. Phase 2 must wire every handler call through an event append.
8. **`stats_snapshot` pulls *today's* rows unconditionally.** At 6am ET before fitbit_sync has run, today's nutrition/recovery rows don't exist, so stats returns nulls. Should fall back to most-recent-non-null.

**Design gaps:**

9. **Zero unit tests.** Plan deferred tests to Phase 3. I now think that's wrong — Phase 2 will refactor and regressions will be hard to catch without tests. **Move tests up to Phase 1.5.**
10. **Dead views** — `latest_body_scan` and `latest_weight` are defined in schema but query.py uses direct SQL. Not a bug, just dead code.
11. **Importer accepts `9999-99-99` as a valid date** — regex doesn't validate calendar correctness.

---

## REVISED NEXT PHASE PLAN (based on self-audit + Hevy question)

Because Phase 1 is incomplete coverage, I'm inserting **Phase 1.5** before Phase 2:

### Phase 1.5 — Coverage + fallback + tests (next session, ~1 focused sit-down)

1. Expand router to ~25 intents covering the actual phrasings that came up in today's conversation log (review `logs/2026-04-11.jsonl` for the real shape of user queries).
2. Extend date-bearing patterns to accept "N days ago" / weekday names. Just hand the token to `dates.resolve_date`, already supported there.
3. Add range intents (weight_range, nutrition_range, training_range, trend queries) and wire `dates.resolve_range` into them.
4. Build `v2/handlers/classify.py` — LLM fallback: router miss → Claude call with strict JSON schema → dispatch to same handlers. Use Haiku 4.5 (cheap, fast, and any hallucinated intent name gets rejected by dispatcher).
5. Fix bugs 4, 5, 8 (exercise fuzzy-match, null-aware averages, stats fallback).
6. Add `v2/tests/` with pytest. Every query function + every router intent. Include a parity test: replay today's real Telegram conversation through v2, verify outputs are at least as good as v1's.
7. Adversarial probing — 30+ "does this fail" queries before commit. Lesson from this session: don't commit based on own-smoke-test success alone.

### Phase 2 — Write path + bot.py cutover (depends on Q1 answer)

**If Hevy = YES:**
- `v2/handlers/ingest_hevy.py` — periodic pull from Hevy API, upsert into workout table
- Hevy API key in env file
- Optional: backfill historical workouts from Hevy if Q1c = A
- `v2/handlers/log.py` — write handlers for `log_weight`, `log_nutrition`, `log_cardio`, `log_body_scan` (no log_workout — Hevy handles it)
- Router write intents for weight/nutrition/cardio/edits only
- Drop the planned "heavy Telegram workout-shorthand parser"
- Drop the planned `rename_exercise` tool (Hevy maintains canonical names)

**If Hevy = NO:**
- `v2/handlers/log.py` — write handlers for all data types including `log_workout`
- Heavy shorthand parser in router (regex grammar for "3x10 320 seated leg press" and its variants)
- `rename_exercise` router intent + handler — the exact thing that was silently dropped at 17:31 ET today

**Common to both paths:**
- `v2/handlers/dexa.py` — pdf2image + Claude vision for DEXA PDFs, writes body_scan rows
- `v2/ingest_fitbit.py` — replaces v1 `fitbit_sync.py`, preserves non-null on partial updates (fixes 2026-04-11 Recovery steps overwrite bug)
- `v2/export_to_sheet.py` — one-way SQLite → read-only Google Sheet push
- `v2/morning_brief.py` — deterministic 7am ET brief from SQLite
- Seed `routine` table (from Q2 answer or from Hevy if Q1=yes)
- Seed `user_facts` table with height, birth_date, goal_weight, goal_bf_pct
- Modify `bot.py` to route through v2 for reads AND writes. **This is the v1 cutover point.** Reversible only via `git revert`.
- Hourly backup cron with 48h/30d/12m retention ladder
- auto-commit.sh updated to also commit a daily `sqlite3 .dump > lifeos.sql` text file (for diff-friendly history)

### Phase 3 — Cleanup + Sonnet swap (unchanged from prior plan)

Delete gog, delete `/home/openclaw/.openclaw/`, delete `auth-heartbeat.sh`, delete `vendored/`, replace sheet export with google-api-python-client, swap to Claude Sonnet, rewrite qa-check.sh, add full test coverage, rewrite architecture.md from scratch for v2, rewrite soul.md as coaching-tone-only, reconsider the openclaw-rename question.

### Phase 4 — Trim and harden (unchanged)

Watch event log for a week, delete checks that never fire, add proactive triggers (no-training-2d, protein-below-70%-3d, weight-wrong-direction-7d).

---

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
