# Audit Playbook

How to run an architectural audit on this system. Methodology and traps — not a checklist of *what* to check (that's in `daily-audit-template.md`).

If you're running an audit, **read this first**, then the daily template.

---

## Pre-audit ritual (read these BEFORE proposing anything)

1. `decisions.log` — last 30 entries. Don't re-litigate already-decided things.
2. `qa-hits.jsonl` (last 14 days) — what's recurring? what's been "fixed" but came back?
3. `soul-proposals.jsonl` — pending proposals the user hasn't seen
4. `claude-sessions/` — most recent session summary, if any
5. `architecture.md` — verify it matches actual system state (v2 is now live)
6. `v2/lifeos.db` — row counts per table, check for test/garbage data

Skipping this step is how you end up recommending things the user already rejected.

---

## Methodology

**Spawn parallel Explore agents on different facets** — file inventory, code audit, persistent bugs, doc coherence. Sequential greps waste time and main-context tokens.

**Verify before acting on agent findings.** Roughly half the "dead code", "TOCTOU", and "redundant function" claims in the 2026-04-11 audit were wrong on re-verification. Treat agent reports as **leads to investigate**, not facts to delete.

**Categorize bugs by fixability:**
- **Architectural** — fixable in code, config, or process. Worth coding for.
- **Model behavior** — the model ignoring its own rules (e.g. `bf_wrong_source`, `said_not_did`). No QA layer can prevent these. Only model swaps fix them. **Don't waste effort patching with code.**

**Root cause vs patch.** If the same bug recurs after a "fix," the fix was a patch. Find the source. The user pushed back hard on patch-job thinking on 2026-04-11 — moving cron from root → openclaw eliminated an entire bug *class* that no amount of monitoring could prevent.

**Options before implementing.** Always present 2–3 options with tradeoffs (tied to integrity > reliability > efficiency) before touching anything. The user explicitly enforces this.

---

## Post-audit ritual

1. **Chown loop** — Claude Code runs as root, every file it edits flips to root ownership. After every session: `sudo chown -R openclaw:openclaw <touched files>` and verify with `find /home/openclaw/lifeos -user root -type f`.
2. **Verify "clean" looks like:** bot service active, `gog sheets get` returns sheet data, qa-check.sh runs with no bash errors (only real flags), zero root-owned files in repo, push to GitHub succeeds.
3. **Log every decision** to `decisions.log` (options, choice, why) — even if it's "DEFERRED — user to decide."
4. **Update `architecture.md` History** with landmark changes only. Tactical fixes go to `git log` and `decisions.log`, NOT arch.md. If History grows past ~15 entries, archive older ones to `history-archive.md`.
5. **Audit-the-audit** — for every issue you found, ask "would `qa-check.sh` have caught this next time?" If no, add a check.

---

## Common traps in this codebase

- **`grep -c ... || echo 0`** in bash produces `"0\n0"` because `grep -c` outputs "0" AND exits 1 on no match. Use `VAR=$(cmd) || VAR=0` instead.
- **Files become root-owned** every time Claude Code edits them (CC runs as root, bot runs as openclaw). qa-check.sh catches it — but the cure is chowning at session end.
- **`/opt/openclaw.env` is load-bearing.** All cron jobs and systemd services source it. Renaming requires touching crontab + service file + scripts in lockstep.
- **The `openclaw` user account name is historical** (from the OpenClaw → bot.py rebuild on 2026-04-05). Treat it as "the lifeos service account." Renaming is purely cosmetic and high coordination cost.
- **SQLite connections can't cross threads.** bot.py uses `asyncio.to_thread` for LLM calls. Any SQLite connection created in the event loop thread CANNOT be used in the worker thread. `ask_ai` must create its own connection. This bit us on 2026-04-12.
- **Never run write-intent queries against the live DB during testing.** On 2026-04-12, adversarial probing with shorthand like "bench 275x5x3" wrote fake data to lifeos.db. Use `--no-llm` with read-only queries, or point tests at an in-memory DB.
- **Verify model IDs against the API before deploying.** On 2026-04-12, hardcoded `claude-sonnet-4-5-20241022` which didn't exist on the API key. Always `curl /v1/models` first.

---

## More traps

- **Conversation history poisoning.** After backend errors are fixed, the bot reloads today's log including error messages. The model may pattern-match on failures and claim things are still broken. Mitigations: (1) clean error entries from the log after fixing, (2) tell user to `/clear`, (3) restart bot. On 2026-04-12 we cleaned 4 broken entries from the log after fixing threading + model ID bugs.
