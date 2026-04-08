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
is_resolved() {
    local key="$1"
    if [ -f "$RESOLVED_FILE" ] && grep -q "\"key\":\"$key\"" "$RESOLVED_FILE" 2>/dev/null; then
        return 0  # resolved
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
    FAILS=$(grep -c "VERIFY FAILED" "$LOG_DIR/$TODAY.jsonl" 2>/dev/null || true)
    if [ "$FAILS" -gt 0 ]; then
        flag_issue "verify_failed_$TODAY" "$FAILS tool verification failures today"
    fi
fi

# --- Check 3: Yesterday's training log exists (unless Sunday off) ---
YESTERDAY_DOW=$(TZ=America/Toronto date -d "yesterday" +%A)
if [ "$YESTERDAY_DOW" != "Sunday" ]; then
    TRAINING=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Training Log!A:A" --account "$GOG_ACCT" --no-input 2>/dev/null | grep -c "$YESTERDAY" || true)
    if [ "$TRAINING" -eq 0 ]; then
        flag_issue "no_training_$YESTERDAY" "No training logged for yesterday ($YESTERDAY, $YESTERDAY_DOW)"
    fi
fi

# --- Check 4: Yesterday's nutrition exists ---
NUTRITION=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Nutrition!A:A" --account "$GOG_ACCT" --no-input 2>/dev/null | grep -c "$YESTERDAY" || true)
if [ "$NUTRITION" -eq 0 ]; then
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

    SAVE_CLAIMS=$(grep -o '"save_memory"' "$YESTERDAY_LOG" 2>/dev/null | wc -l || true)
    SAVE_PROMISES=$(grep -oi 'update.*changelog\|save.*to.*memory\|update.*memory' "$YESTERDAY_LOG" 2>/dev/null | wc -l || true)
    if [ "$SAVE_PROMISES" -gt "$SAVE_CLAIMS" ] && [ "$SAVE_CLAIMS" -gt 0 ]; then
        flag_issue "hallucinated_saves_$YESTERDAY" "Procedure: Bot promised more saves than executed ($SAVE_PROMISES claimed, $SAVE_CLAIMS done)"
    fi

    if grep -qi "how did I do\|status report\|my stats\|morning report" "$YESTERDAY_LOG" 2>/dev/null; then
        TABS_READ=$(grep -o '"tab"[[:space:]]*:[[:space:]]*"[^"]*"' "$YESTERDAY_LOG" 2>/dev/null | sort -u | wc -l || true)
        if [ "$TABS_READ" -lt 3 ]; then
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

# Old OpenClaw service still enabled
if systemctl is-enabled --quiet openclaw 2>/dev/null; then
    flag_issue "orphan_openclaw_service" "Orphan: openclaw.service still enabled (replaced by lifeos-bot)"
fi

# Memory files older than 30 days with no recent reads in logs
for f in "$REPO_DIR"/memory/*.md; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    age_days=$(( ($(date +%s) - $(stat -c %Y "$f")) / 86400 ))
    if [ "$age_days" -gt 30 ]; then
        # Check if any log in last 7 days references this file
        recent_use=$(grep -rl "$fname" "$LOG_DIR"/ 2>/dev/null | tail -7 | wc -l || true)
        if [ "$recent_use" -eq 0 ]; then
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
    UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l || true)
    if [ "$UNCOMMITTED" -gt 20 ]; then
        flag_issue "git_uncommitted" "Architecture: $UNCOMMITTED uncommitted changes (auto-commit may be failing)"
    fi
fi

# --- Check 12: Morning brief delivered today ---
BRIEF_LOG="$REPO_DIR/morning-brief.log"
if [ -f "$BRIEF_LOG" ]; then
    # Log appends "Morning brief sent (Nnn chars)" on success
    BRIEF_SENT=$(tail -1 "$BRIEF_LOG" 2>/dev/null | grep -c "Morning brief sent" || true)
    if [ "$BRIEF_SENT" -eq 0 ]; then
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

# --- Check 15: Fitbit data freshness (not just timer running) ---
RECOVERY_LATEST=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Recovery!A:A" --account "$GOG_ACCT" --no-input 2>/dev/null \
    | grep -oP '^\d{4}-\d{2}-\d{2}' | sort | tail -1 || true)
if [ -n "$RECOVERY_LATEST" ]; then
    RECOVERY_AGE=$(( ($(date +%s) - $(date -d "$RECOVERY_LATEST" +%s)) / 86400 ))
    if [ "$RECOVERY_AGE" -gt 2 ]; then
        flag_issue "fitbit_stale" "Fitbit data stale: last Recovery entry is $RECOVERY_LATEST (${RECOVERY_AGE}d ago)"
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

# --- Check 18: Sleep data freshness ---
SLEEP_LATEST=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Recovery!A:B" --account "$GOG_ACCT" --no-input 2>/dev/null \
    | grep -P '^\d{4}-\d{2}-\d{2}\s+\d' | tail -1 | awk '{print $1}' || true)
if [ -n "$SLEEP_LATEST" ]; then
    SLEEP_AGE=$(( ($(date +%s) - $(date -d "$SLEEP_LATEST" +%s)) / 86400 ))
    if [ "$SLEEP_AGE" -gt 2 ]; then
        flag_issue "sleep_stale" "Sleep data stale: last scored night is $SLEEP_LATEST (${SLEEP_AGE}d ago) — ring/watch may not be worn"
    fi
fi

# --- Check 19: Git remote reachable ---
cd "$REPO_DIR"
if ! git ls-remote --exit-code origin HEAD > /dev/null 2>&1; then
    # Check if pushes have been silently failing
    LOCAL_HEAD=$(git rev-parse HEAD 2>/dev/null || true)
    REMOTE_HEAD=$(git ls-remote origin HEAD 2>/dev/null | awk '{print $1}' || true)
    if [ -n "$LOCAL_HEAD" ] && [ -n "$REMOTE_HEAD" ] && [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
        flag_issue "git_remote_behind" "Git remote is behind local — pushes may be failing"
    elif [ -z "$REMOTE_HEAD" ]; then
        flag_issue "git_remote_unreachable" "Cannot reach git remote — backup is not updating"
    fi
fi

# --- Check 20: Tool result errors not surfaced to user ---
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    # Look for Permission denied, ERROR, FAILED in tool results where bot didn't tell user
    TOOL_ERRORS=$(grep -oP '"result"\s*:\s*"[^"]*(?:Permission denied|ERROR|FAILED)[^"]*"' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l || true)
    if [ "$TOOL_ERRORS" -gt 0 ]; then
        # Check if bot mentioned the error to user
        ERROR_MENTIONS=$(grep -ci "permission denied\|error.*tool\|failed.*save\|could not write" "$LOG_DIR/$TODAY.jsonl" 2>/dev/null || true)
        if [ "$TOOL_ERRORS" -gt "$ERROR_MENTIONS" ]; then
            flag_issue "silent_tool_errors_$TODAY" "$TOOL_ERRORS tool errors today, only $ERROR_MENTIONS surfaced to user"
        fi
    fi
fi

# --- Check 21: Memory file permissions ---
MEMORY_FILE="$REPO_DIR/memory/memory.md"
if [ -f "$MEMORY_FILE" ]; then
    MEMORY_OWNER=$(stat -c '%U' "$MEMORY_FILE")
    if [ "$MEMORY_OWNER" != "openclaw" ]; then
        flag_issue "memory_perms" "memory.md owned by $MEMORY_OWNER (should be openclaw) — bot cannot write"
    fi
fi

# --- Check 22: Said-vs-did — bot claimed actions without matching tool calls ---
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    # Count times bot said "logged" or "saved" in assistant text
    CLAIMED=$(grep -oP '"assistant"\s*:\s*"[^"]*(?:Logged|logged|Saved|saved to memory|saved to sheet)[^"]*"' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l || true)
    # Count actual tool calls
    TOOL_CALLS=$(grep -oP '"tool"\s*:\s*"(?:log_workout|log_weight|log_nutrition|save_memory|write_sheet)"' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l || true)
    if [ "$CLAIMED" -gt 0 ] && [ "$TOOL_CALLS" -eq 0 ]; then
        flag_issue "said_not_did_$TODAY" "Bot claimed $CLAIMED log/save actions but made $TOOL_CALLS tool calls"
    fi
fi

# --- Check 23: Exercise count mismatch — bot's stated total vs actual logged exercises ---
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    # Count unique exercise names the bot mentioned logging
    EXERCISES_MENTIONED=$(grep -oP '"assistant"[^}]*(?:Pull Ups|Lat Pull|Cable Row|Reverse Pec|Preacher|Treadmill|Bench|Squat|Leg Press|Leg Curl|Leg Extension|Shoulder Press|Cable Fl|Cable Raise|Captain Chair)[^"]*logged' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l || true)
    # Count actual log_workout calls
    EXERCISES_LOGGED=$(grep -oP '"tool"\s*:\s*"log_workout"' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l || true)
    if [ "$EXERCISES_MENTIONED" -gt 0 ] && [ "$EXERCISES_LOGGED" -eq 0 ]; then
        flag_issue "exercises_not_logged_$TODAY" "Bot discussed logging exercises but no log_workout calls found"
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
