# LifeOS History Archive

Archived from `architecture.md` on 2026-04-11 during the lean sweep. These entries are tactical fixes, superseded approaches, or historical curiosities that no longer describe how the system currently works. The canonical system map (`architecture.md`) keeps only landmark architectural decisions.

If an entry below describes something that **does** reflect current state, move it back to `architecture.md`. If a future audit needs to know "why was X done in early April 2026?" — start here.

The full audit trail also lives in:
- `git log` — every code/config change with diffs
- `decisions.log` — every "X over Y, because Z"

---

## 2026-04-05

- **Initially used Claude Sonnet ($12/mo), switched to Grok 4.1 Fast ($0.50/mo).** Grok's problems were caused by the broken OpenClaw sandbox, not the model itself. With direct file access Grok 4.1 worked at 24x lower cost. (Later swaps see entries below.)
- **Injected current date/time into system prompt dynamically.** Grok had no clock — it was guessing day-of-week wrong (mapped Saturday to Wednesday). Now every message includes `Current date/time: ...` at the top.
- **Added tool audit trail to conversation logs.** Bot said it would update CHANGELOG.md but only called save_memory once. Tool log catches claims vs actual actions.
- **Added procedures.md.** Defined the "correct path" for each operation so QA could check compliance. Consolidated into soul.md on 2026-04-07 — separate file caused instruction drift.
- **Added sync_fitbit tool for on-demand pulls.** Fitbit syncs 3x/day but user wanted fresh data on demand. Bot couldn't call systemctl, so the tool runs the sync script directly.
- **Added sync timestamps to Fitbit data (Notes column).** Without timestamps, no way to tell today's data from yesterday's stale sync.
- **Rebranded to J.A.R.V.I.S., scrubbed all personal info, squashed git history, pushed to GitHub (public).** Open source for community review. Personal info stays in env file only.
- **Consolidated into single git repo with hourly auto-commit + push.** Full audit trail. Any AI can `git log` to see every change.
- **Orphan cleanup.** Removed old `/home/openclaw/lifeos-bot/`, Docker sandbox container + images (99MB), OpenClaw subdirectories (agents, canvas, cron, devices, identity, logs, media, sandbox, tasks, telegram, credentials), stale workspace files. Kept the gog binary and Google auth config.

## 2026-04-06

- **Fixed `grep -c || echo "0"` bug in qa-check.sh.** `grep -c` outputs "0" AND exits non-zero on no-match, so `|| echo "0"` appended a second "0". Changed to `|| true`. (Superseded by 2026-04-11 lean sweep — final pattern is `VAR=$(cmd) || VAR=0`.)
- **Switched AI model from Grok 4.1 Fast to Grok 4.20.** Hallucination concerns with the cheaper model. (Reverted in subsequent swaps.)
- **Expanded QA from 11 to 19 checks.** Added: morning brief delivery, disk space, RAM, Fitbit data freshness, Google Sheets auth, Caddy health, sleep data freshness, git remote reachable. Also added `qa-hits.jsonl` so the monthly audit can report which checks fire often vs never.
- **Added QA effectiveness audit to monthly-audit.sh.** A check that never fires in 3 months is either perfectly reliable or broken — monthly review surfaces it.
- **Removed anti-hallucination response stripping from conversation reload.** Bot now loads its own full responses on restart. The stripping meant the bot didn't know what it had committed to. Hallucination risk now mitigated by daily QA + end-of-day audit.
- **Fixed memory.md ownership (root → openclaw).** Bot couldn't write to memory.md. (Recurring root-cause bug — finally fixed structurally on 2026-04-11 by migrating cron from root to openclaw.)
- **Updated soul.md routine: Seated Cable Rows → Cable Rows.** User-approved swap; memory save had failed due to permission bug.
- **Added QA checks 20–23** (silent tool errors, memory permissions, said-vs-did, exercise count mismatch).
- **Added daily-audit-template.md.** End-of-day Claude Code audit checklist. (Rewritten on 2026-04-11 from 252 → 61 LOC.)
- **Added multi-agent mode switching to bot.py.** Admin mode (GPT-4.1-nano) for daily ops, Research mode (Grok 4.20-reasoning) for deep reasoning. User switches with "switch to research"/"switch back". (Removed in later cleanup — multi-agent caused identity confusion.)
- **Added tool failure safety net to bot.py.** `_append_failure_notice()` auto-appends a notice if the bot's reply doesn't mention tool errors. Two-layer: emphatic error from `execute_tool` + post-hoc notice on the reply.
- **Three architectural fixes to dual-agent system.** Conversation filtering per agent, one-shot escalation (instead of permanent mode flip), agent names moved to env. Root cause: both agents shared one conversation stream and were seeing each other's responses as their own.
- **Swapped admin model from Grok 4.1 Fast Reasoning → GPT-4.1-nano** ($0.10/$0.40). Grok was hallucinating tool calls.
- **Added `clear_row` tool + row numbers in `read_sheet` output.** Bot was clearing wrong rows because read_sheet returned sorted data with no row positions. (After this: Grok 4.1 cleared row 3 / Leg Curls from 04-04 by mistake — data unrecoverable.)
- **Added `research` tool — calls Grok 4.20 for deep reasoning.** Admin model handles tool calling, research handles factual accuracy. (Removed when multi-agent was rolled back.)
- **Added Cardio tab to Google Sheet + `log_cardio` tool.** Bot was hacking cardio into log_workout (reps=minutes, weight=speed) producing garbage data.
- **Saved workout logging decisions to memory.md.** Varying reps → multi-row, unilateral → per-side labels, cardio algorithm. These were agreed in conversation but never persisted due to the permission bug.

## 2026-04-07

- **Added "How You Think" section to soul.md.** Data integrity and self-verification principles. (Removed in 2026-04-08 trim from 116 → 51 LOC.)
- **Added "Where Things Go" section to soul.md.** Routing rules so the bot knew the difference between behavioral rules (soul) and user decisions (memory). (Removed in 2026-04-08 trim.)
- **Fixed conversation reload to include tool history.** `load_conversation_from_logs()` was stripping tool calls/results — after a restart the model had no idea what it had actually done.
- **Fixed sheet append column drift.** Switched gog sheets append from INSERT_ROWS → OVERWRITE. Also tightened `_verify_sheet_write` to check column position, not just string presence anywhere in the row. (Superseded 2026-04-09 by switching to targeted `gog sheets update`.)
- **Added empty response retry and 429 rate limit backoff to ask_ai().** Grok was returning empty content and 429 errors that got dumped raw to the user.
- **Removed workout approval step.** Extra round-trip that got missed. Bot now logs immediately and shows what was logged.
- **Switched AI model from Grok 4.20 → grok-4-1-fast-reasoning** ($0.20/$0.50). With reasoning principles in soul.md and code-level safety nets, the cheaper model was acceptable.

## 2026-04-08

- **Applied 3 soul proposals.** (1) Auto-sync Fitbit on stale queries. (2) Discretionary communication formatting. (3) Show previous session's performance on workout routines.
- **Tightened said-vs-did warning regex.** Removed overly broad patterns matching past-tense and future-tense — 5 false positives in one session.
- **Fixed `fitbit_sync.py` INSERT_ROWS → OVERWRITE.** Same column drift bug fixed in bot.py on 04-07; fitbit_sync.py was missed because it lives outside the repo (`/home/openclaw/fitbit_sync.py`).
- **Fixed `fitbit_sync.py` sleep score field.** Was using `efficiency` (% time in bed asleep) instead of Fitbit's actual Sleep Score.
- **Refined write-hallucination regex** to require "just"/"now" qualifier on "I've/I have" patterns.
- **Cleared 15 phantom workout rows from Training Log.** Bot triple-logged a 04-08 leg session because user sent workout data in stages and each got logged additively.
- **Expanded daily audit template** with intent-vs-action, decisions.log cross-reference, and "audit the audit" sections. (Rewritten 2026-04-11 to 61 LOC.)
- **Fixed memory.md ownership again** (root → openclaw). Same recurring bug — Claude Code sessions running as root flipped ownership. (Finally fixed structurally 2026-04-11 by migrating cron from root to openclaw and chowning at session end.)

## 2026-04-09

- **Hardened `_verify_sheet_write`** to retry once after 2s on initial failure. **Hardened `_find_next_row`** to log warnings on blank-row gaps (monitoring, not intervention). Fixed a blank row in Cardio tab that was causing column drift.
