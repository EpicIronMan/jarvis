#!/usr/bin/env bash
# Daily QA check — runs via cron, alerts the user only if unresolved issues found.
# Zero tokens. Pure bash. Checks data integrity, procedures, and architecture.
# Skips issues that match entries in resolved.jsonl.
# Hit tracking: each flag_issue call logs to qa-hits.jsonl for monthly audit.

set -euo pipefail

source /opt/openclaw.env
BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
CHAT_ID="${CHAT_ID}"
GOG="${GOG_PATH:-/usr/local/bin/gog}"
GOG_ACCT="${GOG_ACCOUNT}"
SHEET_ID="${SHEET_ID}"
REPO_DIR="/home/openclaw/lifeos"
LOG_DIR="$REPO_DIR/logs"
RESOLVED_FILE="$REPO_DIR/resolved.jsonl"
HITS_FILE="$REPO_DIR/qa-hits.jsonl"
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)
ISSUES=""

export HOME=/home/openclaw
export GOG_ACCOUNT="$GOG_ACCT"
export GOG_KEYRING_PASSWORD="${GOG_KEYRING_PASSWORD:-}"

# --- Helper: check if an issue key is already resolved ---
# Match exact key only — substring match would let "no_training" auto-resolve
# "no_training_2026-04-05" etc. The trailing literal pattern requires the
# closing quote to come right after the key.
is_resolved() {
    local key="$1"
    if [ -f "$RESOLVED_FILE" ] && grep -qF "\"key\":\"$key\"," "$RESOLVED_FILE" 2>/dev/null; then
        return 0  # resolved
    fi
    if [ -f "$RESOLVED_FILE" ] && grep -qF "\"key\":\"$key\"}" "$RESOLVED_FILE" 2>/dev/null; then
        return 0  # resolved (last field on line)
    fi
    return 1  # not resolved
}

# --- Helper: add an issue only if not resolved ---
# Also logs every hit (resolved or not) to qa-hits.jsonl for monthly audit.
flag_issue() {
    local key="$1"
    local msg="$2"
    echo "{\"date\":\"$TODAY\",\"key\":\"$key\",\"msg\":\"$msg\"}" >> "$HITS_FILE"
    if ! is_resolved "$key"; then
        ISSUES="${ISSUES}\n- $msg"
    fi
}

# --- Check 1: Conversation log exists for today ---
if [ ! -f "$LOG_DIR/$TODAY.jsonl" ]; then
    flag_issue "no_convo_log" "No conversation log for today ($TODAY)"
fi

# --- Check 2: Tool verification failures in today's log ---
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    FAILS=$(grep -c "VERIFY FAILED" "$LOG_DIR/$TODAY.jsonl" 2>/dev/null) || FAILS=0
    if (( FAILS > 0 )); then
        flag_issue "verify_failed_$TODAY" "$FAILS tool verification failures today"
    fi
fi

# --- Check 3: Yesterday's training log exists (unless Sunday off) ---
YESTERDAY_DOW=$(TZ=America/Toronto date -d "yesterday" +%A)
if [ "$YESTERDAY_DOW" != "Sunday" ]; then
    TRAINING=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Training Log!A:A" --account "$GOG_ACCT" --no-input 2>/dev/null | grep -c "$YESTERDAY") || TRAINING=0
    if (( TRAINING == 0 )); then
        flag_issue "no_training_$YESTERDAY" "No training logged for yesterday ($YESTERDAY, $YESTERDAY_DOW)"
    fi
fi

# --- Check 4: Yesterday's nutrition exists ---
NUTRITION=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Nutrition!A:A" --account "$GOG_ACCT" --no-input 2>/dev/null | grep -c "$YESTERDAY") || NUTRITION=0
if (( NUTRITION == 0 )); then
    flag_issue "no_nutrition_$YESTERDAY" "No nutrition logged for yesterday ($YESTERDAY)"
fi

# --- Check 5: Weight logged in last 3 days ---
WEIGHT_LINES=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Body Metrics!A:B" --account "$GOG_ACCT" --no-input 2>/dev/null | tail -3)
LATEST_DATE=$(echo "$WEIGHT_LINES" | tail -1 | awk '{print $1}')
if [ -z "$LATEST_DATE" ] || [ "$LATEST_DATE" = "Date" ]; then
    flag_issue "no_weight_data" "No weight data found in Body Metrics"
fi

# --- Check 6: Bot service is running ---
if ! systemctl is-active --quiet lifeos-bot; then
    flag_issue "bot_down" "lifeos-bot service is NOT running"
fi

# --- Check 7: Fitbit sync health ---
if ! systemctl is-active --quiet fitbit-sync.timer; then
    flag_issue "fitbit_timer_down" "fitbit-sync.timer is NOT active"
fi

# --- Check 8: Procedure compliance (scan yesterday's tool log) ---
YESTERDAY_LOG="$LOG_DIR/$YESTERDAY.jsonl"
if [ -f "$YESTERDAY_LOG" ]; then
    if grep -q "body fat\|BF%\|body composition\|lean mass" "$YESTERDAY_LOG" 2>/dev/null; then
        if ! grep -q '"tab".*Body Scans\|"tab": "Body Scans"' "$YESTERDAY_LOG" 2>/dev/null; then
            flag_issue "bf_wrong_source" "Procedure: Bot discussed BF% but never read Body Scans tab"
        fi
    fi

    SAVE_CLAIMS=$(grep -o '"save_memory"' "$YESTERDAY_LOG" 2>/dev/null | wc -l) || SAVE_CLAIMS=0
    SAVE_PROMISES=$(grep -oi 'update.*changelog\|save.*to.*memory\|update.*memory' "$YESTERDAY_LOG" 2>/dev/null | wc -l) || SAVE_PROMISES=0
    if (( SAVE_PROMISES > SAVE_CLAIMS && SAVE_CLAIMS > 0 )); then
        flag_issue "hallucinated_saves_$YESTERDAY" "Procedure: Bot promised more saves than executed ($SAVE_PROMISES claimed, $SAVE_CLAIMS done)"
    fi

    if grep -qi "how did I do\|status report\|my stats\|morning report" "$YESTERDAY_LOG" 2>/dev/null; then
        TABS_READ=$(grep -o '"tab"[[:space:]]*:[[:space:]]*"[^"]*"' "$YESTERDAY_LOG" 2>/dev/null | sort -u | wc -l) || TABS_READ=0
        if (( TABS_READ < 3 )); then
            flag_issue "incomplete_report_$YESTERDAY" "Procedure: Status report only read $TABS_READ sheet tabs (expected 3+)"
        fi
    fi
fi

# --- Check 9: Orphan detection ---
# Empty directories
for dir in "$REPO_DIR"/*/; do
    if [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ]; then
        dirname=$(basename "$dir")
        flag_issue "empty_dir_$dirname" "Orphan: Empty directory $dirname/"
    fi
done

# (removed: Check 9b orphan_openclaw_service — migration completed 2026-04-05,
# never fired in qa-hits, deleted 2026-04-11 audit pass)

# Memory files older than 30 days with no recent reads in logs
for f in "$REPO_DIR"/memory/*.md; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    age_days=$(( ($(date +%s) - $(stat -c %Y "$f")) / 86400 ))
    if [ "$age_days" -gt 30 ]; then
        # Check if any log in last 7 days references this file
        recent_use=$(grep -rl "$fname" "$LOG_DIR"/ 2>/dev/null | tail -7 | wc -l) || recent_use=0
        if (( recent_use == 0 )); then
            flag_issue "stale_memory_$fname" "Orphan: memory/$fname not modified in ${age_days}d and not referenced in recent logs"
        fi
    fi
done

# --- Check 10: Architecture drift ---
for f in bot.py soul.md morning-brief-ai.py architecture.md qa-check.sh auto-commit.sh; do
    if [ ! -f "$REPO_DIR/$f" ]; then
        flag_issue "missing_file_$f" "Architecture: Missing expected file $f"
    fi
done

# --- Check 11: Git repo health (retry once if index.lock exists) ---
cd "$REPO_DIR"
if [ -f .git/index.lock ]; then
    sleep 5
fi
if ! git status --porcelain > /dev/null 2>&1; then
    flag_issue "git_broken" "Architecture: Git repo broken or missing"
else
    UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l) || UNCOMMITTED=0
    if (( UNCOMMITTED > 20 )); then
        flag_issue "git_uncommitted" "Architecture: $UNCOMMITTED uncommitted changes (auto-commit may be failing)"
    fi
fi

# --- Check 12: Morning brief delivered today ---
BRIEF_LOG="$REPO_DIR/morning-brief.log"
if [ -f "$BRIEF_LOG" ]; then
    # Log appends "Morning brief sent (Nnn chars)" on success
    BRIEF_SENT=$(tail -1 "$BRIEF_LOG" 2>/dev/null | grep -c "Morning brief sent") || BRIEF_SENT=0
    if (( BRIEF_SENT == 0 )); then
        flag_issue "brief_not_sent" "Morning brief did not send today (check morning-brief.log)"
    fi
else
    flag_issue "brief_no_log" "Morning brief log missing entirely"
fi

# --- Check 13: Disk space ---
DISK_PCT=$(df / --output=pcent | tail -1 | tr -d ' %')
if [ "$DISK_PCT" -gt 85 ]; then
    flag_issue "disk_high" "Disk usage at ${DISK_PCT}% (threshold 85%)"
fi

# --- Check 14: Memory (RAM) ---
MEM_PCT=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
if [ "$MEM_PCT" -gt 85 ]; then
    flag_issue "ram_high" "RAM usage at ${MEM_PCT}% (threshold 85%)"
fi

# --- Check 15+18: Fitbit + sleep freshness (one fetch, two signals) ---
# Fitbit health check has two failure modes that need different alerts:
#   (a) No Recovery rows at all → sync is broken
#   (b) Rows exist but sleep score column blank → ring/watch not worn
# Previously two separate gog calls; merged into one read 2026-04-11.
RECOVERY_DATA=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Recovery!A:B" --account "$GOG_ACCT" --no-input 2>/dev/null) || RECOVERY_DATA=""
RECOVERY_LATEST=$(echo "$RECOVERY_DATA" | grep -oP '^\d{4}-\d{2}-\d{2}' | sort | tail -1 || true)
if [ -n "$RECOVERY_LATEST" ]; then
    RECOVERY_AGE=$(( ($(date +%s) - $(date -d "$RECOVERY_LATEST" +%s)) / 86400 ))
    if (( RECOVERY_AGE > 2 )); then
        flag_issue "fitbit_stale" "Fitbit data stale: last Recovery entry is $RECOVERY_LATEST (${RECOVERY_AGE}d ago)"
    fi
    # Sleep score check only meaningful if Fitbit syncing at all
    SLEEP_LATEST=$(echo "$RECOVERY_DATA" | grep -P '^\d{4}-\d{2}-\d{2}\s+\d' | tail -1 | awk '{print $1}' || true)
    if [ -n "$SLEEP_LATEST" ]; then
        SLEEP_AGE=$(( ($(date +%s) - $(date -d "$SLEEP_LATEST" +%s)) / 86400 ))
        if (( SLEEP_AGE > 2 )); then
            flag_issue "sleep_stale" "Sleep data stale: last scored night is $SLEEP_LATEST (${SLEEP_AGE}d ago) — ring/watch may not be worn"
        fi
    fi
else
    flag_issue "fitbit_no_data" "Could not read Recovery tab — Fitbit data may be missing"
fi

# --- Check 16: Google Sheets auth health ---
GOG_TEST=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Body Metrics!A1:A1" --account "$GOG_ACCT" --no-input 2>&1 || true)
if echo "$GOG_TEST" | grep -qi "token\|auth\|expired\|error\|no TTY"; then
    flag_issue "gog_auth_broken" "Google Sheets auth may be broken: $(echo "$GOG_TEST" | head -1)"
fi

# --- Check 17: Caddy web server health ---
if systemctl is-active --quiet caddy; then
    CADDY_RESP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost 2>/dev/null || echo "000")
    if [ "$CADDY_RESP" = "000" ]; then
        flag_issue "caddy_no_response" "Caddy running but not responding on localhost"
    fi
else
    flag_issue "caddy_down" "Caddy service is not running"
fi

# --- Check 19: Git remote reachable ---
cd "$REPO_DIR"
# Compare local HEAD to remote HEAD to detect push failures.
# Avoid git ls-remote twice — if first call fails, that IS the signal.
LOCAL_HEAD=$(git rev-parse HEAD 2>/dev/null || true)
REMOTE_HEAD=$(git ls-remote origin HEAD 2>/dev/null | awk '{print $1}' || true)
if [ -z "$REMOTE_HEAD" ]; then
    flag_issue "git_remote_unreachable" "Cannot reach git remote — backup is not updating"
elif [ -n "$LOCAL_HEAD" ] && [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
    flag_issue "git_remote_behind" "Git remote is behind local — pushes may be failing"
fi

# --- Check 20: Tool result errors not surfaced to user ---
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    # Look for Permission denied, ERROR, FAILED in tool results where bot didn't tell user
    TOOL_ERRORS=$(grep -oP '"result"\s*:\s*"[^"]*(?:Permission denied|ERROR|FAILED)[^"]*"' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l) || TOOL_ERRORS=0
    if (( TOOL_ERRORS > 0 )); then
        # Check if bot mentioned the error to user
        ERROR_MENTIONS=$(grep -ci "permission denied\|error.*tool\|failed.*save\|could not write" "$LOG_DIR/$TODAY.jsonl" 2>/dev/null) || ERROR_MENTIONS=0
        if (( TOOL_ERRORS > ERROR_MENTIONS )); then
            flag_issue "silent_tool_errors_$TODAY" "$TOOL_ERRORS tool errors today, only $ERROR_MENTIONS surfaced to user"
        fi
    fi
fi

# --- Check 21: File ownership drift (bot can't write files owned by root) ---
# Any file the bot or cron jobs need to write must be owned by openclaw.
# After 2026-04-11 audit, all cron jobs run as openclaw, so this should now
# only fire if Claude Code (root) edited a repo file directly.
for f in memory/memory.md architecture.md bot.py daily-audit-template.md soul.md soul-proposals.jsonl resolved.jsonl decisions.log; do
    path="$REPO_DIR/$f"
    [ -f "$path" ] || continue
    owner=$(stat -c '%U' "$path")
    if [ "$owner" != "openclaw" ]; then
        key="ownership_$(echo "$f" | tr '/.' '__')"
        flag_issue "$key" "$f owned by $owner (should be openclaw) — bot cannot write"
    fi
done

# --- Check 22: Said-vs-did — bot claimed actions without matching tool calls ---
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    # Count times bot said "logged" or "saved" in assistant text
    CLAIMED=$(grep -oP '"assistant"\s*:\s*"[^"]*(?:Logged|logged|Saved|saved to memory|saved to sheet)[^"]*"' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l) || CLAIMED=0
    # Count actual tool calls
    TOOL_CALLS=$(grep -oP '"tool"\s*:\s*"(?:log_workout|log_weight|log_nutrition|save_memory|write_sheet)"' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l) || TOOL_CALLS=0
    if (( CLAIMED > 0 && TOOL_CALLS == 0 )); then
        flag_issue "said_not_did_$TODAY" "Bot claimed $CLAIMED log/save actions but made $TOOL_CALLS tool calls"
    fi
fi

# --- Check 23: Exercise count mismatch — bot's stated total vs actual logged exercises ---
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    # Count unique exercise names the bot mentioned logging
    EXERCISES_MENTIONED=$(grep -oP '"assistant"[^}]*(?:Pull Ups|Lat Pull|Cable Row|Reverse Pec|Preacher|Treadmill|Bench|Squat|Leg Press|Leg Curl|Leg Extension|Shoulder Press|Cable Fl|Cable Raise|Captain Chair)[^"]*logged' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l) || EXERCISES_MENTIONED=0
    # Count actual log_workout calls
    EXERCISES_LOGGED=$(grep -oP '"tool"\s*:\s*"log_workout"' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l) || EXERCISES_LOGGED=0
    if (( EXERCISES_MENTIONED > 0 && EXERCISES_LOGGED == 0 )); then
        flag_issue "exercises_not_logged_$TODAY" "Bot discussed logging exercises but no log_workout calls found"
    fi
fi

# --- Check 25: Said-failed-not-tried — bot claimed tool failure without trying it ---
# Mirror of Check 22. After a backend fix, the bot can pattern-match on prior
# failure messages in the conversation history and claim "still broken" without
# actually calling the tool. Flag when assistant text mentions failure language
# but the entry has zero tool calls.
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    FAILED_CLAIMS=$(python3 -c "
import json, re, sys
path = '$LOG_DIR/$TODAY.jsonl'
fail_pat = re.compile(r'(?:token revoked|sheets? down|sheet access is down|cannot read|can.t read|auth.*broken|invalid.grant|access denied|permission denied|unable to.*sheet|backend fix|external fix needed)', re.I)
n = 0
try:
    for line in open(path):
        line = line.strip()
        if not line: continue
        try: e = json.loads(line)
        except: continue
        a = e.get('assistant') or ''
        tools = e.get('tools') or []
        if fail_pat.search(a) and len(tools) == 0:
            n += 1
except FileNotFoundError:
    pass
print(n)
" 2>/dev/null) || FAILED_CLAIMS=0
    if (( FAILED_CLAIMS > 0 )); then
        flag_issue "said_failed_not_tried_$TODAY" "Bot claimed tool failure $FAILED_CLAIMS time(s) without making any tool call (likely model context bias from prior failures — user should /clear after backend fixes)"
    fi
fi

# --- Check 24: Stale soul proposals ---
PROPOSALS_FILE="$REPO_DIR/soul-proposals.jsonl"
if [ -f "$PROPOSALS_FILE" ]; then
    PENDING=$(grep -c '"status"[^}]*"pending"' "$PROPOSALS_FILE" 2>/dev/null) || PENDING=0
    AWAITING=$(grep -c '"status"[^}]*"awaiting_user"' "$PROPOSALS_FILE" 2>/dev/null) || AWAITING=0
    STALE_COUNT=$((PENDING + AWAITING))
    if (( STALE_COUNT > 5 )); then
        flag_issue "stale_soul_proposals" "$STALE_COUNT pending/awaiting soul proposals — review may not be running or user not responding"
    fi
fi

# --- Send alert if unresolved issues found ---
if [ -n "$ISSUES" ]; then
    MSG=$(printf "*QA Check — %s*\n\nIssues found:\n%b\n\nReview or ask J.A.R.V.I.S. to investigate." "$TODAY" "$ISSUES")
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="${CHAT_ID}" \
        -d parse_mode="Markdown" \
        --data-urlencode "text=${MSG}" > /dev/null
    echo "QA alert sent: $ISSUES"
else
    echo "QA check passed — no unresolved issues."
fi
