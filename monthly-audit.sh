#!/usr/bin/env bash
# J.A.R.V.I.S. Monthly Architecture Audit
# Runs on the 1st of each month via cron. Gathers data and sends
# a summary to Telegram. Zero tokens — pure bash.
# The user reviews the report and discusses findings with Jarvis.

set -euo pipefail

source /opt/openclaw.env
BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
CHAT_ID="${CHAT_ID}"
REPO_DIR="/home/openclaw/lifeos"
LOG_DIR="$REPO_DIR/logs"
RESOLVED_FILE="$REPO_DIR/resolved.jsonl"
MONTH=$(TZ=America/Toronto date +%Y-%m)
PREV_MONTH=$(TZ=America/Toronto date -d "last month" +%Y-%m)

export HOME=/home/openclaw

# --- 1. Git activity this month ---
cd "$REPO_DIR"
COMMITS=$(git log --oneline --since="$PREV_MONTH-28" 2>/dev/null | wc -l || echo "0")
COMMIT_SUMMARY=$(git log --oneline --since="$PREV_MONTH-28" 2>/dev/null | head -10)

# --- 2. QA alerts this month ---
QA_LOG="$REPO_DIR/qa-check.log"
QA_ALERTS=0
if [ -f "$QA_LOG" ]; then
    QA_ALERTS=$(grep -c "QA alert sent" "$QA_LOG" 2>/dev/null || echo "0")
fi

# --- 3. Resolved issues ---
RESOLVED_COUNT=0
RESOLVED_ITEMS=""
if [ -f "$RESOLVED_FILE" ] && [ -s "$RESOLVED_FILE" ]; then
    RESOLVED_COUNT=$(wc -l < "$RESOLVED_FILE")
    RESOLVED_ITEMS=$(cat "$RESOLVED_FILE" | head -10)
fi

# --- 4. Memory files health ---
MEMORY_COUNT=$(ls "$REPO_DIR/memory/"*.md 2>/dev/null | wc -l || echo "0")
STALE_MEMORY=""
for f in "$REPO_DIR"/memory/*.md; do
    [ -f "$f" ] || continue
    age_days=$(( ($(date +%s) - $(stat -c %Y "$f")) / 86400 ))
    if [ "$age_days" -gt 30 ]; then
        STALE_MEMORY="${STALE_MEMORY}\n  - $(basename "$f") (${age_days}d old)"
    fi
done

# --- 5. Conversation volume ---
CONV_DAYS=$(ls "$LOG_DIR"/*.jsonl 2>/dev/null | wc -l || echo "0")
TOTAL_MESSAGES=0
if [ "$CONV_DAYS" -gt 0 ]; then
    TOTAL_MESSAGES=$(cat "$LOG_DIR"/*.jsonl 2>/dev/null | wc -l || echo "0")
fi

# --- 6. Services health ---
BOT_STATUS=$(systemctl is-active lifeos-bot 2>/dev/null || echo "unknown")
FITBIT_STATUS=$(systemctl is-active fitbit-sync.timer 2>/dev/null || echo "unknown")

# --- 7. Disk usage ---
REPO_SIZE=$(du -sh "$REPO_DIR" 2>/dev/null | awk '{print $1}')
LOGS_SIZE=$(du -sh "$LOG_DIR" 2>/dev/null | awk '{print $1}')

# --- 8. Orphan quick check ---
ORPHANS=""
EMPTY_DIRS=$(find "$REPO_DIR" -type d -empty -not -path "*/.git/*" -not -path "*/venv/*" 2>/dev/null)
if [ -n "$EMPTY_DIRS" ]; then
    ORPHANS="${ORPHANS}\n  - Empty dirs: $(echo "$EMPTY_DIRS" | wc -l)"
fi
if systemctl is-enabled --quiet openclaw 2>/dev/null; then
    ORPHANS="${ORPHANS}\n  - openclaw.service still enabled"
fi

# --- Build report ---
MSG=$(cat <<EOF
*J.A.R.V.I.S. Monthly Audit — ${MONTH}*

*Activity*
- $COMMITS commits this month
- $CONV_DAYS days with conversations
- $TOTAL_MESSAGES total messages

*Services*
- Bot: $BOT_STATUS
- Fitbit sync: $FITBIT_STATUS

*QA Summary*
- $QA_ALERTS alerts triggered this month
- $RESOLVED_COUNT issues resolved

*Memory Files*
- $MEMORY_COUNT files in memory/
$([ -n "$STALE_MEMORY" ] && printf "- Stale (30d+):%b" "$STALE_MEMORY" || echo "- None stale")

*Disk*
- Repo: $REPO_SIZE
- Logs: $LOGS_SIZE

$([ -n "$ORPHANS" ] && printf "*Orphans Found*%b" "$ORPHANS" || echo "*No orphans detected*")

*Recent Changes*
$(echo "$COMMIT_SUMMARY" | head -5)

*Review Checklist*
Reply to discuss any of these:
1. Is architecture.md still coherent?
2. Are we using the best/cheapest tools?
3. Any recurring QA issues to address?
4. Any features to add or remove?
5. Any stale files or procedures?
EOF
)

# --- Send ---
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d chat_id="${CHAT_ID}" \
    -d parse_mode="Markdown" \
    --data-urlencode "text=${MSG}" > /dev/null

echo "Monthly audit sent for $MONTH"
