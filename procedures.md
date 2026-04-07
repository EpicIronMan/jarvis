# LifeOS — Expected Procedures

These are the correct tool call patterns for common operations. The QA system checks the tool log against these rules. If the bot consistently deviates, the procedure may need updating — not just the bot.

Last updated: 2026-04-05

## Data Source Rules

| Data Point | Correct Source | Wrong Source | Why |
|-----------|---------------|-------------|-----|
| Body fat % | Body Scans tab (DEXA rows only) | Body Metrics (Renpho BF%) | DEXA is ground truth, Renpho BF% is inaccurate |
| Lean mass | Body Scans tab (latest DEXA) | Hardcoded in prompt | Must use live data, updates with each new DEXA |
| Protein target | Calculated from latest DEXA lean mass | Hardcoded number | Recalculates when new DEXA arrives |
| Current weight | Body Metrics tab (latest row) | Conversation memory | Sheet is source of truth |
| Today's workout | soul.md routine + current date/time | Guessing the day | Date is injected into system prompt |
| Training history | Training Log tab | Conversation memory | Sheet has all data |
| Nutrition | Nutrition tab | Conversation memory | Sheet has all data |

## Expected Tool Calls by Operation

### "How did I do?" / Status report
1. `read_sheet` → Training Log (recent rows)
2. `read_sheet` → Body Metrics (recent rows)
3. `read_sheet` → Nutrition (recent rows)
4. `read_sheet` → Body Scans (for DEXA BF% — should NOT use Body Metrics BF%)
5. `read_sheet` → Recovery (if available)

If any of these are missing, the report is incomplete.

### Log a workout
1. AI parses the input and logs immediately via `log_workout`
2. Tool result should contain `[VERIFIED]`
3. AI shows what was logged (exercises, weight, sets, reps, volume) — user corrects if needed

### Log weight
1. `log_weight` → Body Metrics (writes row)
2. Tool result should contain `[VERIFIED]`

### Discuss body fat / body composition
1. `read_sheet` → Body Scans (DEXA data)
2. Should NOT call `read_sheet` → Body Metrics for BF%
3. If comparing over time, should read multiple DEXA rows

### Upload DEXA scan
1. `upload_to_drive` → Google Drive
2. `read_sheet` → Body Scans (get previous DEXA for comparison)
3. Report changes vs previous scan
4. Recalculate protein target from new lean mass

### Save routine change
1. `save_memory` → writes the file
2. Tool result should contain `[VERIFIED]`
3. If the bot says it will update multiple files, there should be matching tool calls for each

## Deviation Handling

If the bot does something outside these procedures, the QA system flags it. **No one auto-fixes it.** The process is:

1. QA check flags the deviation in the daily Telegram alert
2. the user reviews with an AI (Claude Code, the bot itself, or both)
3. Discussion: is the procedure wrong, or is the bot wrong?
4. the user decides: update the procedure, fix the bot, or leave it
5. Changes are committed with reasoning in the git message

Deviations are not bugs by default — they're signals for review.
