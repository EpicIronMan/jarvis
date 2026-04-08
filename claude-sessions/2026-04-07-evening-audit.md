# Evening Audit — April 7, 2026

## What was done this session

1. **soul.md consolidated** — Merged procedures.md and operational rules from memory.md into soul.md. Added "How You Think" (data integrity principles), "Data Sources" (explicit mapping), "Workout Logging" (varying reps, unilateral), "Cardio Logging" (ACSM formula, caching), "Where Things Go" (bot knows where to put things). Deleted procedures.md. Cleaned memory.md to only user decisions.
2. **Conversation reload fixed** — `load_conversation_from_logs()` now includes tool call history so model can verify its own past work across restarts.
3. **Empty response retry + 429 backoff** — Code-level handling for API failures the model can't self-correct.
4. **Workout approval removed** — soul.md, bot.py tool description, and procedures.md (before deletion) all updated. Bot logs immediately, shows summary.
5. **Sheet append column drift fixed** — Switched INSERT_ROWS to OVERWRITE mode. Root cause: blank rows + INSERT_ROWS caused data to shift 5+ columns right. Restored all Apr 4-6 data, cleared misaligned Apr 7 junk, re-logged Apr 7 workout.
6. **Verify function fixed** — Added `-p` flag for tab-delimited output (was splitting on tabs but gog defaults to spaces). Also tightened to check column position (date in A, field in B) not just string presence.
7. **Failure notice gap fixed** — `_append_failure_notice` now catches `VERIFY FAILED` in tool results.
8. **Model downgraded** — grok-4.20 ($2/$6) → grok-4-1-fast-reasoning ($0.20/$0.50). 10x cheaper. Issues today were laziness not capability.
9. **architecture.md updated** — All procedures.md references updated, changelog entries for all 8 changes.
10. **decisions.log updated** — 4 entries: consolidation, model downgrade, append mode, approval removal.

## Audit Results

### 1. Said vs Did

| Bot claimed | Tool call? | Result | Notes |
|---|---|---|---|
| Synced Fitbit (08:56) | YES | OK | |
| Logged 4 exercises (14:05) | YES | [VERIFIED] but wrong columns | INSERT_ROWS bug |
| Updated cardio to 284 (14:10) | YES write_sheet | [VERIFIED] | |
| Saved 3 memory entries | YES save_memory x3 | [VERIFIED] | Now in soul.md |
| Re-logged 4 exercises (15:19) | YES | [VERIFIED] but wrong columns | Duplicate |
| Re-logged AGAIN (15:30) | YES | [VERIFIED] but wrong columns | Triple duplicate |
| Logged 65lb DB press (15:32) | YES | [VERIFIED] | Wrong columns |
| "Standardized to 280" (14:09) | NO tool call | HALLUCINATED | ⚠️ notice fired |
| "Here's what I saved" (14:14) | read_memory only | No write | ⚠️ notice fired |
| Logged deadlift (23:14) | YES | [VERIFY FAILED] | Data fine — verify code bug |
| Synced Fitbit (17:35) | YES | OK | |

### 2. Logic & Reasoning

- 284 net cal (ACSM 45min/3.5mph/3.5%) — correct but was 280 first (inconsistent)
- Volume math — all correct
- TDEE ~2,476 (RMR×1.2 + cardio + training) — reasonable, grounded
- Date hallucination in morning brief — called Apr 6 "today"
- "No change" for weight — misleading, should say "no new measurement"

### 3. Data Integrity (verified against sheet)

All April 7 data now correct in sheet:
- 5 training exercises in correct columns (6,945 lbs + 3,375 deadlift)
- Treadmill 45min / 284 cal
- Nutrition 1,238 cal / 168g protein (Fitbit)

### 4. Over-Restriction Audit

No over-restrictions found. All code-level interventions are either API-level (model can't handle) or monitoring (flag, don't intervene).

### 5. Summary

- **Session quality:** 2/5 (morning rough, afternoon recovered)
- **Critical failures:** 2 (verify lying all day, date hallucination)
- **Backfills needed:** 4 (all done)
- **Guardrails added:** 0
- **Over-restrictions found:** 0
- **Model trend:** Improving — cheaper model handled afternoon/evening well after structural fixes. Issues were architecture not capability.

## Key insight

Approach used for every fix: "Why is the AI making the mistake?" then "Why can't the AI catch it on its own?" If the answer is a code blocker, fix the code. If the answer is laziness, add a reasoning principle to soul.md. Don't add specific guardrails for things the model should reason through.
