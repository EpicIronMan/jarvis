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

## Summary

- **Session quality:** (1-5 score)
- **Critical failures:** (count)
- **Backfills needed:** (count)
- **Guardrails added:** (count)
- **Over-restrictions found:** (count — rules that should be replaced by model reasoning + tools)
- **Model trend:** (improving / stable / declining)
