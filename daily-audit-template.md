# Daily Telegram Bot Audit Template

Run at end of day with Claude Code. Feed today's conversation log and walk through each section.

**Log file:** `/home/openclaw/lifeos/logs/YYYY-MM-DD.jsonl`

---

## 1. Said vs Did

For every action the bot claimed to take, verify a matching tool call exists in the log.

| Bot claimed | Tool call exists? | Tool result OK? | Notes |
|-------------|-------------------|-----------------|-------|
| (fill per session) | YES/NO | VERIFIED/FAILED/ERROR | |

**Red flags:** Bot says "logged" / "saved" / "done" with no tool call. Tool returned error but bot said success.

---

## 2. Logic & Reasoning Check

Review the bot's calculations, recommendations, and data interpretations.

| Claim | Correct? | Issue | 
|-------|----------|-------|
| (fill per session) | YES/NO | (describe if wrong) |

**Check for:**
- Volume math (sets × reps × weight)
- Calorie/MET calculations
- Body fat source (must be DEXA/Body Scans, not Body Metrics)
- Protein target derived from latest lean mass
- TDEE calculations using RMR 1,618

---

## 3. Memory & Retention

Did the bot remember what it should from earlier in the session and from memory.md?

| Expected knowledge | Remembered? | Source |
|-------------------|-------------|--------|
| Current routine | YES/NO | soul.md / memory.md |
| Routine swaps (Leg Press, Cable Rows) | YES/NO | memory.md |
| Logging rules (varying reps, unilateral) | YES/NO | memory.md |
| Cardio algorithm | YES/NO | memory.md |
| User's stats (weight, BF%, RMR) | YES/NO | sheets |

**Check:** Did the bot call `read_memory` when it should have? Did it save new decisions that should persist?

---

## 4. Compliance & Approvals

Did the bot follow the approval rule? Did it act without confirmation where required?

| Action | Approval required? | Approval given? | Notes |
|--------|-------------------|-----------------|-------|
| (fill per session) | YES/NO | YES/NO/SKIPPED | |

---

## 5. Data Integrity

Spot-check the sheet data against what the bot claimed to write.

```bash
# Pull today's training log
gog sheets get "$SHEET_ID" "Training Log!A:J" --account "$GOG_ACCT" | grep "YYYY-MM-DD"
```

| Expected row | In sheet? | Correct values? |
|-------------|-----------|-----------------|
| (fill per session) | YES/NO | YES/NO |

**Blank row check:** For each tab that was written to today, scan column A for blank rows between data rows. Blank rows cause column drift on future writes.
```bash
gog sheets get "$SHEET_ID" "TAB!A:A" --account "$GOG_ACCT" -p
```
If blank rows exist between data rows, fix immediately (shift data up, clear orphan row).

---

## 5.5 Conversation Review & Soul/Memory Routing

Three tiers — run the appropriate one based on the cycle. Update `audit-state.json` bookmarks after each tier.

### A. Incremental (every audit)

Read conversation logs from the `audit-state.json` daily bookmark to now.

**A1. Intent vs Action** — For every user request, did the bot do what the user actually meant?

| Timestamp | User said | What user meant | What bot did | Correct? | Notes |
|-----------|-----------|----------------|-------------|----------|-------|
| | | | | YES/NO | |

**Check for:**
- Bot misinterpreted units, exercises, dates, or context
- Bot did the right tool call but with wrong values
- Bot answered a different question than what was asked
- Bot acknowledged a request but never acted on it

**A2. Routing** — For every directive, rule, correction, or algorithm:

| Timestamp | User said | Type | Bot action | Correct destination | Correct? | Notes |
|-----------|-----------|------|------------|-------------------|----------|-------|
| | | directive/fact/correction/algorithm | propose_soul_change / save_memory / neither | soul / memory | YES/NO | |

**Check for:**
- Directives routed to save_memory instead of propose_soul_change (mis-route)
- Soul-type rules the bot acknowledged but didn't route anywhere (missed route)
- Proposals that are actually just facts/preferences (should be memory)
- Corrections the user gave that the bot just acknowledged without persisting anywhere

After checking, update `audit-state.json` daily bookmark:
```bash
python3 -c "
import json, datetime
from zoneinfo import ZoneInfo
now = datetime.datetime.now(ZoneInfo('America/Toronto')).isoformat()
path = '/home/openclaw/lifeos/audit-state.json'
try:
    state = json.load(open(path))
except: state = {}
state['daily'] = {'last_run': now}
json.dump(state, open(path, 'w'), indent=2)
"
```

### B. Pattern scan (weekly — run on Sundays or when weekly bookmark is >7 days old)

Read last 7 days of conversation logs. Look for recurring patterns:

| Pattern | First seen | Count | Status | Action needed? |
|---------|-----------|-------|--------|---------------|
| Same instruction given 2+ times | | | User had to repeat = bot didn't learn | Should be a soul proposal |
| Soul proposal filed then rejected | | | | Was the directive unclear? |
| Memory entries that are actually rules | | | | Promote to soul proposal |
| Bot follows a rule inconsistently | | | | Needs stronger soul.md wording |
| Things tried and reverted | | | | Document why in decisions.log |

Update `audit-state.json` weekly bookmark after completing.

### C. Deep review (monthly — run on 1st or when monthly bookmark is >30 days old)

Full sweep comparing soul.md against actual usage over the past month:

1. Read all soul proposals from the month (approved, rejected, pending)
2. Read soul.md — is each rule actually followed in practice?
3. Scan logs for implicit rules the user expects but aren't in soul.md
4. Check for soul.md rules that are never triggered (dead rules)
5. Check memory.md for entries that should have been soul proposals
6. Diff soul.md against 30-day-old version — any drift, dilution, or contradiction?
7. Cross-reference decisions.log — are we re-litigating decisions already made? Are there old decisions whose context has changed (new architecture, different model) that might be worth revisiting?
8. Look for approaches tried and abandoned in past months — did conditions change enough to retry?

| soul.md rule | Followed in practice? | Still needed? | Notes |
|-------------|----------------------|--------------|-------|
| (fill per section) | YES/NO/PARTIALLY | YES/NO | |

**Pending proposals:** (count in soul-proposals.jsonl not yet reviewed)
**Mis-routes found this period:** (count)
**Missed routes found this period:** (count)

Update `audit-state.json` monthly bookmark after completing.

---

## 6. Backfill Actions

List anything that needs to be fixed or backfilled based on this audit.

| Issue | Fix | Who |
|-------|-----|-----|
| (fill per session) | (describe fix) | Telegram bot / Claude Code |

After fixing, tell the Telegram bot to execute the backfill. This tests that the fix works.

---

## 7. Model Intuition Tracking

Track whether the bot is improving over time. No guardrails added — just observations.

| Observation | Positive/Negative | Pattern? |
|-------------|-------------------|----------|
| (fill per session) | +/- | First time / Repeat |

**Monthly rollup:** Review these observations. If a negative pattern repeats 3+ times, consider adding a guardrail. If a positive pattern holds, note it as learned behavior.

---

## 8. Over-Restriction Audit

Are we blocking the models from reasoning? Code-level rules that do what the model should do are restrictions. Monitoring that flags issues without intervening is not.

| Code/rule | What it does | Restricts model? | Should the model handle this instead? |
|-----------|-------------|-----------------|--------------------------------------|
| (scan bot.py for regex, hardcoded logic, auto-interventions) | (describe) | YES/NO | YES/NO — why |

**Check for:**
- Regex or keyword matching that replaces model reasoning (e.g., intent detection the model could do via a tool)
- Auto-escalation that silently replaces the model's response with another model's response
- System prompt rules that tell the model NOT to do something instead of giving it a tool to do it properly
- Conversation filtering or stripping that hides context the model needs to reason well
- Safety nets that intervene (change flow) vs safety nets that monitor (flag to user)

**Principle:** Monitor heavily, intervene rarely. If a rule exists because the model hallucinated, ask: was the hallucination caused by bad architecture (conversation soup, missing tools) or bad model quality? Fix the architecture first. Only add code-level restrictions if the model genuinely can't handle it after architecture is clean.

**Action:** If any restriction is found that the model could handle via a tool or cleaner prompt, flag it for removal in section 9 backfills.

---

## 9. Guardrails Added (if any)

Only add guardrails when a pattern repeats. Document what was added and why.

| Guardrail | Why added | Where (soul.md / bot.py / qa-check.sh) |
|-----------|-----------|----------------------------------------|
| (fill if needed) | (pattern that triggered it) | |

---

## 10. Audit the Audit

After every fix or issue found in this session, ask: **would this audit template have caught it?** If not, add a check right now.

| Issue found this session | Which audit section should catch it? | Does that section exist? | Added? |
|-------------------------|-------------------------------------|------------------------|--------|
| (fill per session) | | YES/NO | YES/NO — describe what was added |

**Also check:**
- Did any section feel redundant or never produce findings? Flag for removal in monthly review.
- Did the auditor (Claude Code) skip a section or do it superficially? Note which and why.
- Were there findings from casual conversation that the structured sections missed? That's a gap — add a check.

**Principle:** The audit template is a living document. Every session should leave it slightly better than it was found.

---

## Summary

- **Session quality:** (1-5 score)
- **Critical failures:** (count)
- **Backfills needed:** (count)
- **Guardrails added:** (count)
- **Over-restrictions found:** (count — rules that should be replaced by model reasoning + tools)
- **Audit template changes:** (count — checks added/modified this session)
- **Model trend:** (improving / stable / declining)
