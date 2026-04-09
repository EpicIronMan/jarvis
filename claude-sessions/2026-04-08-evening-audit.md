# Evening Audit — April 8, 2026

## What was done this session

1. **fitbit_sync.py INSERT_ROWS → OVERWRITE** — Same column drift bug fixed in bot.py on April 7, missed in fitbit_sync.py (lives outside repo).
2. **fitbit_sync.py sleep score fix** — Was using `efficiency` (% time asleep) instead of Fitbit's actual `score` field. Now prefers `main.get("score", efficiency)` with fallback.
3. **Write hallucination regex refined** — Removed overly broad past-tense pattern (`(updated|logged|...) (the|your|it|row|...)`) that matched descriptions of already-verified writes. Kept present/future patterns + required "just"/"now" qualifier on "I've/I have" pattern. Eliminated 2 false positives from today's session.
4. **qa-hits.jsonl ownership fixed** — Was root:root, QA check failed with permission denied. Fixed to openclaw:openclaw.
5. **architecture.md updated** — Changelog entries for fitbit_sync.py OVERWRITE fix.

## Audit Results

### 1. Said vs Did

| Bot claimed | Tool call? | Result | Notes |
|---|---|---|---|
| Cleared deadlift test (00:44) | YES clear_row | [VERIFIED] | |
| Synced Fitbit on sleep query (10:08) | YES sync_fitbit | OK | New soul rule working |
| Logged 4 exercises (11:26) | YES log_workout | [VERIFIED] 15,120 lbs | |
| Cleared 2 Renpho rows (11:09) | YES clear_row | [VERIFIED] | User confirmed 173.1 correct |
| "PR logged" / "Day complete" (11:05-06) | NO write tool | False claim x3 | ⚠️ warnings fired — but 2 were false positives (past-tense refs) |
| "50k total vol" (16:39-16:47) | read_sheet only | Misleading | Referenced phantom rows already cleared |

### 2. Logic & Reasoning

- Sleep: 5.3hrs = 315min (76+161+56+22) — correct math
- Sleep score: 93 (efficiency) vs 76 (app Sleep Score) — **wrong field used in code** (fixed)
- Volume math: all correct (7680+3000+4200+240 = 15,120)
- "50k vol" narrative: **stale** — kept referencing phantom rows post-cleanup
- Protein target 154-180g from DEXA lean mass 128.6lbs × 1.2-1.4 — correct

### 3. Data Integrity (verified against sheet)

All April 8 data correct:
- 4 training exercises in correct columns (15,120 lbs total)
- No phantom rows remaining
- Body Metrics: 173.1 lbs single Fitbit row (Renpho dupes cleared)
- Recovery: 93/5.3hrs/3834 steps/61 RHR
- Nutrition: 1325 cal / 105g protein

### 4. Compliance

No violations. Destructive actions (clear rows) all had user approval.

### 5. Intent vs Action Issues

- Bot took 3 tries to give today's routine with prior weights
- "Pyramid" narrative from earlier bled into unrelated responses
- Sleep score complaint: bot explained the discrepancy but never investigated whether the data source was wrong (it was)
- User said "writing in a way I don't understand" — communication soul proposal applied mid-session, improved after

### 6. Over-Restriction Audit

No over-restrictions found. Both monitors (failure notice, write hallucination) are passive.

### 7. QA Check Results

- "Bot discussed BF% but never read Body Scans tab"
- "Bot promised more saves than executed (4 claimed, 3 done)"

### 8. Summary

- **Session quality:** 3/5 (data integrity good, communication rough, intent misreads)
- **Critical failures:** 1 (stale 50k vol narrative)
- **Backfills needed:** 0 (sleep score fix is code-level, applied)
- **Guardrails added:** 0
- **Over-restrictions found:** 0
- **Code fixes:** 4 (INSERT_ROWS, sleep score field, regex refinement, qa-hits permission)
- **Model trend:** Stable — monitoring working, soul proposals working, multi-turn intent still weak

## Post-Audit Changes (same session)

6. **soul.md radical trim** — 116 lines → ~50 lines. Removed all communication rules, meta-reasoning ("How You Think"), routing decision tree ("Where Things Go"), auto-sync rule, volume reporting, prior performance display, decisions.log check, sanity-check instruction. Kept: identity, user stats, approval rule, DEXA ground truth, data sources, workout/cardio parsing, notes columns, goals, routine. Added one-line routing for propose_soul_change.
7. **Model swap: grok-4-1-fast-reasoning → gpt-4.1-mini** — Grok fast model spoke in fragments ("Done—rest/nutrition. Protein check. Weight 173.1 good. Sleep soon?") even after constraint trim. That's the model's natural style, not fixable via prompt. GPT-4.1-mini ($0.40/$1.60) speaks naturally and has reliable tool calling. User confirmed "better" on first test.
8. **decisions.log** — 3 new entries: sleep score field, write hallucination regex, soul.md radical trim.
9. **architecture.md** — 4 new changelog entries: sleep score fix, regex refinement, fitbit_sync OVERWRITE, soul.md trim.

## Key insights

1. Sleep score discrepancy was a **code bug**, not a model bug — pulling `efficiency` instead of `score` from Fitbit API. Lesson: when user says data is wrong, check the pipeline code first.
2. Constraint bloat degrades cheap models more than expensive ones — soul.md went from 116 lines of rules to 50 lines of essentials. Well-documented in LLM research ("lost in the middle", instruction overload, alignment tax).
3. Model quality matters independently of prompt quality — grok-4-1-fast-reasoning spoke in fragments regardless of prompt length. The right fix was changing models, not adding a "speak naturally" rule.
4. Two changes on the same day (April 7: constraint additions + model downgrade) masked each other's effects. Lesson: one variable at a time.
