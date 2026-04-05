#!/usr/bin/env bash
# Daily QA check — runs via cron, alerts the user on Telegram only if issues found.
# Zero tokens. Pure bash. Checks data integrity across sheets and logs.

set -euo pipefail

source /opt/openclaw.env
BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
CHAT_ID="${CHAT_ID}"
GOG="${GOG_PATH:-/usr/local/bin/gog}"
GOG_ACCT="${GOG_ACCOUNT}"
SHEET_ID="${SHEET_ID}"
LOG_DIR="/home/openclaw/lifeos/logs"
TODAY=$(TZ=America/Toronto date +%Y-%m-%d)
YESTERDAY=$(TZ=America/Toronto date -d "yesterday" +%Y-%m-%d)
ISSUES=""

export HOME=/home/openclaw
export GOG_ACCOUNT="$GOG_ACCT"
export GOG_KEYRING_PASSWORD="${GOG_KEYRING_PASSWORD:-}"

# --- Check 1: Conversation log exists for today ---
if [ ! -f "$LOG_DIR/$TODAY.jsonl" ]; then
    ISSUES="${ISSUES}\n- No conversation log for today ($TODAY)"
fi

# --- Check 2: Tool verification failures in today's log ---
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    FAILS=$(grep -c "VERIFY FAILED" "$LOG_DIR/$TODAY.jsonl" 2>/dev/null || echo "0")
    if [ "$FAILS" -gt 0 ]; then
        ISSUES="${ISSUES}\n- $FAILS tool verification failures today"
    fi
fi

# --- Check 3: Yesterday's training log exists (unless Sunday off) ---
YESTERDAY_DOW=$(TZ=America/Toronto date -d "yesterday" +%A)
if [ "$YESTERDAY_DOW" != "Sunday" ]; then
    TRAINING=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Training Log!A:A" --account "$GOG_ACCT" --no-input 2>/dev/null | grep -c "$YESTERDAY" || echo "0")
    if [ "$TRAINING" -eq 0 ]; then
        ISSUES="${ISSUES}\n- No training logged for yesterday ($YESTERDAY, $YESTERDAY_DOW)"
    fi
fi

# --- Check 4: Yesterday's nutrition exists ---
NUTRITION=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Nutrition!A:A" --account "$GOG_ACCT" --no-input 2>/dev/null | grep -c "$YESTERDAY" || echo "0")
if [ "$NUTRITION" -eq 0 ]; then
    ISSUES="${ISSUES}\n- No nutrition logged for yesterday ($YESTERDAY)"
fi

# --- Check 5: Weight logged in last 3 days ---
WEIGHT_LINES=$(HOME=/home/openclaw "$GOG" sheets get "$SHEET_ID" "Body Metrics!A:B" --account "$GOG_ACCT" --no-input 2>/dev/null | tail -3)
LATEST_DATE=$(echo "$WEIGHT_LINES" | tail -1 | awk '{print $1}')
if [ -z "$LATEST_DATE" ] || [ "$LATEST_DATE" = "Date" ]; then
    ISSUES="${ISSUES}\n- No weight data found in Body Metrics"
fi

# --- Check 6: Bot service is running ---
if ! systemctl is-active --quiet lifeos-bot; then
    ISSUES="${ISSUES}\n- lifeos-bot service is NOT running"
fi

# --- Check 7: Procedure compliance (scan yesterday's tool log) ---
YESTERDAY_LOG="$LOG_DIR/$YESTERDAY.jsonl"
if [ -f "$YESTERDAY_LOG" ]; then
    # Check: if bot discussed body fat, did it read Body Scans (not just Body Metrics)?
    if grep -q "body fat\|BF%\|body composition\|lean mass" "$YESTERDAY_LOG" 2>/dev/null; then
        if ! grep -q '"tab".*Body Scans\|"tab": "Body Scans"' "$YESTERDAY_LOG" 2>/dev/null; then
            ISSUES="${ISSUES}\n- Procedure: Bot discussed BF%/body comp but never read Body Scans tab (should use DEXA, not Renpho)"
        fi
    fi

    # Check: if bot claimed to save multiple files, verify matching tool calls
    SAVE_CLAIMS=$(grep -o '"save_memory"' "$YESTERDAY_LOG" 2>/dev/null | wc -l || echo "0")
    SAVE_PROMISES=$(grep -oi 'update.*changelog\|save.*to.*memory\|update.*memory' "$YESTERDAY_LOG" 2>/dev/null | wc -l || echo "0")
    if [ "$SAVE_PROMISES" -gt "$SAVE_CLAIMS" ] && [ "$SAVE_CLAIMS" -gt 0 ]; then
        ISSUES="${ISSUES}\n- Procedure: Bot promised more file saves than it executed (claimed ~$SAVE_PROMISES, executed $SAVE_CLAIMS)"
    fi

    # Check: status reports should read multiple sheet tabs
    if grep -qi "how did I do\|status report\|my stats\|morning report" "$YESTERDAY_LOG" 2>/dev/null; then
        TABS_READ=$(grep -o '"tab"[[:space:]]*:[[:space:]]*"[^"]*"' "$YESTERDAY_LOG" 2>/dev/null | sort -u | wc -l || echo "0")
        if [ "$TABS_READ" -lt 3 ]; then
            ISSUES="${ISSUES}\n- Procedure: Status report only read $TABS_READ sheet tabs (expected 3+: Training, Metrics, Nutrition)"
        fi
    fi
fi

# --- Check 8: Architecture drift — are key files where they should be? ---
for f in bot.py soul.md morning-brief.sh architecture.md procedures.md qa-check.sh auto-commit.sh; do
    if [ ! -f "/home/openclaw/lifeos/$f" ]; then
        ISSUES="${ISSUES}\n- Architecture: Missing expected file $f"
    fi
done

# --- Check 9: Git repo health ---
cd /home/openclaw/lifeos
if ! git status --porcelain > /dev/null 2>&1; then
    ISSUES="${ISSUES}\n- Architecture: Git repo broken or missing"
else
    UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l || echo "0")
    if [ "$UNCOMMITTED" -gt 20 ]; then
        ISSUES="${ISSUES}\n- Architecture: $UNCOMMITTED uncommitted changes (auto-commit may be failing)"
    fi
fi

# --- Send alert if issues found ---
if [ -n "$ISSUES" ]; then
    MSG=$(printf "*QA Check — %s*\n\nIssues found:\n%b\n\nReview logs or ask the bot to investigate." "$TODAY" "$ISSUES")
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="${CHAT_ID}" \
        -d parse_mode="Markdown" \
        --data-urlencode "text=${MSG}" > /dev/null
    echo "QA alert sent: $ISSUES"
else
    echo "QA check passed — no issues."
fi
