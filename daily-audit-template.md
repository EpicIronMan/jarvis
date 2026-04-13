# Daily Telegram Bot Audit

What `qa-check.sh` can't catch automatically. Run with Claude Code at end of day.

> **Before starting any audit (daily, weekly, or one-off):** read `audit-playbook.md`. It covers the pre-audit ritual, methodology (parallel agents, verify before acting, bug taxonomy), post-audit verification, and the codebase-specific traps that bite every time.

**Log file:** `/home/openclaw/lifeos/logs/YYYY-MM-DD.jsonl`

**Already automated** (do NOT repeat here): said-vs-did, BF source, training/nutrition logged, ownership drift, tool errors, hallucinated saves, exercise count mismatch, stale soul proposals. See the QA Checks table in `architecture.md` — anything covered there is qa-check.sh's job, not this audit's.

This audit only does the things automation **can't** do: judgment calls about intent, restrictions, and the audit itself.

---

## 1. Intent vs Action

For each user request, did the bot do what the user actually meant — not just what it was asked literally?

| Timestamp | User said | What user meant | What bot did | Correct? |
|-----------|-----------|----------------|--------------|----------|

**Watch for:**
- Misinterpreted units, exercises, dates, context
- Right tool, wrong values
- Answered a different question than what was asked
- Acknowledged a request but never acted on it

This is the only thing qa-check.sh fundamentally can't do — it doesn't know what the user *meant*.

---

## 2. Over-Restriction Sweep (Musk's Algorithm)

Apply Elon Musk's 5-step algorithm in order:

1. **Question the requirement** — Who added this rule/code? Why? Is it still valid?
2. **Delete** — Remove more than feels comfortable. If you don't add back 10%, you didn't delete enough.
3. **Simplify** — Only AFTER deleting. Don't optimize a thing that should not exist.
4. **Accelerate** — Only after 1-3.
5. **Automate** — Last, not first.

| Restriction | Where (file:line) | Step 1: Why does this exist? | Step 2: Delete? | Step 3: Simplify? |
|-------------|-------------------|------------------------------|-----------------|-------------------|

**Principle:** If the LLM already understands something (natural language, intent, context), don't put deterministic code in front of it. Deterministic layers should only handle what actually needs to be deterministic (timezone math, schema enforcement, ACID writes). Code that intercepts and fails is worse than no code at all.

---

## 3. Audit the Audit

For every fix or finding from this session, ask: **would `qa-check.sh` have caught it next time?** If no, add a check.

| Issue found this session | Caught by qa-check today? | Check added (where) |
|-------------------------|---------------------------|---------------------|

**Also check:**
- Did any section in this template never produce a finding two audits in a row? Delete it.
- Were there findings from casual conversation that the structured sections missed? That's a gap — add a check.

The audit is a living tool, not an heirloom. Every session should leave it slightly better than it was found.

---

## Summary

- Critical failures:
- Over-restrictions found:
- Audit changes (checks added / template edits):
- Model trend (improving / stable / declining):
