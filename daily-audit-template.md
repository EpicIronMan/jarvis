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

## 2. Over-Restriction Sweep

Are any rules in `soul.md`, `bot.py`, or `qa-check.sh` doing what the model should be doing?

| Restriction | Where (file:line) | Could the model handle this via tool/prompt? | Remove? |
|-------------|-------------------|----------------------------------------------|---------|

**Principle:** Monitor heavily, intervene rarely. Code-level rules that replace model reasoning are restrictions; checks that flag without intervening are not. If a rule exists because the model hallucinated, ask: was the cause bad architecture (missing tools, conversation soup) or bad model? **Fix architecture first.** Add code restrictions only when the model genuinely can't handle it after architecture is clean.

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
