#!/usr/bin/env bash
# Daily QA check — runs via cron, alerts the user only if unresolved issues found.
# Zero tokens. Pure bash. Checks data integrity, procedures, and architecture.
# Skips issues that match entries in resolved.jsonl.

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
TODAY=$(TZ=America/Toronto date +%Y-%m-%d)
YESTERDAY=$(TZ=America/Toronto date -d "yesterday" +%Y-%m-%d)
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
flag_issue() {
    local key="$1"
    local msg="$2"
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
    FAILS=$(grep -c "VERIFY FAILED" "$LOG_DIR/$TODAY.jsonl" 2>/dev/null || echo "0")
    if [ "$FAILS" -gt 0 ]; then
        flag_issue "verify_failed_$TODAY" "$FAILS tool verification failures today"
    fi
fi

# --- Check 3: Yesterday's training log exists (unless Sunday off) ---
YESTERDAY_DOW=$(TZ=America/Toronto date -d "yesterday" +%A)
if [ "$YESTERDAY_DOW" != "Sunday" ]; then
    TRAINING=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Training Log!A:A" --account "$GOG_ACCT" --no-input 2>/dev/null | grep -c "$YESTERDAY" || echo "0")
    if [ "$TRAINING" -eq 0 ]; then
        flag_issue "no_training_$YESTERDAY" "No training logged for yesterday ($YESTERDAY, $YESTERDAY_DOW)"
    fi
fi

# --- Check 4: Yesterday's nutrition exists ---
NUTRITION=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Nutrition!A:A" --account "$GOG_ACCT" --no-input 2>/dev/null | grep -c "$YESTERDAY" || echo "0")
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

    SAVE_CLAIMS=$(grep -o '"save_memory"' "$YESTERDAY_LOG" 2>/dev/null | wc -l || echo "0")
    SAVE_PROMISES=$(grep -oi 'update.*changelog\|save.*to.*memory\|update.*memory' "$YESTERDAY_LOG" 2>/dev/null | wc -l || echo "0")
    if [ "$SAVE_PROMISES" -gt "$SAVE_CLAIMS" ] && [ "$SAVE_CLAIMS" -gt 0 ]; then
        flag_issue "hallucinated_saves_$YESTERDAY" "Procedure: Bot promised more saves than executed ($SAVE_PROMISES claimed, $SAVE_CLAIMS done)"
    fi

    if grep -qi "how did I do\|status report\|my stats\|morning report" "$YESTERDAY_LOG" 2>/dev/null; then
        TABS_READ=$(grep -o '"tab"[[:space:]]*:[[:space:]]*"[^"]*"' "$YESTERDAY_LOG" 2>/dev/null | sort -u | wc -l || echo "0")
        if [ "$TABS_READ" -lt 3 ]; then
            flag_issue "incomplete_report_$YESTERDAY" "Procedure: Status report only read $TABS_READ sheet tabs (expected 3+)"
        fi
    fi
fi

# --- Check 9: Architecture drift ---
for f in bot.py soul.md morning-brief.sh architecture.md procedures.md qa-check.sh auto-commit.sh; do
    if [ ! -f "$REPO_DIR/$f" ]; then
        flag_issue "missing_file_$f" "Architecture: Missing expected file $f"
    fi
done

# --- Check 10: Git repo health ---
cd "$REPO_DIR"
if ! git status --porcelain > /dev/null 2>&1; then
    flag_issue "git_broken" "Architecture: Git repo broken or missing"
else
    UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l || echo "0")
    if [ "$UNCOMMITTED" -gt 20 ]; then
        flag_issue "git_uncommitted" "Architecture: $UNCOMMITTED uncommitted changes (auto-commit may be failing)"
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
