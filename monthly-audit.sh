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
MONTH=$(date +%Y-%m)
PREV_MONTH=$(date -d "last month" +%Y-%m)

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

# --- 9. QA check effectiveness audit ---
HITS_FILE="$REPO_DIR/qa-hits.jsonl"
QA_EFFECTIVENESS=""
if [ -f "$HITS_FILE" ] && [ -s "$HITS_FILE" ]; then
    # Count hits per check key (strip date suffixes for grouping)
    # e.g. "no_training_2026-04-05" -> "no_training"
    MONTH_HITS=$(grep "\"date\":\"$PREV_MONTH" "$HITS_FILE" 2>/dev/null || true)
    if [ -n "$MONTH_HITS" ]; then
        # Group by base key (remove trailing _YYYY-MM-DD)
        HIT_SUMMARY=$(echo "$MONTH_HITS" | grep -oP '"key":"[^"]*"' | sed 's/"key":"//;s/"$//' \
            | sed 's/_[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}$//' | sort | uniq -c | sort -rn | head -10)
        QA_EFFECTIVENESS="$HIT_SUMMARY"
    fi
fi

# Checks that NEVER fired this month (candidates for review)
# All known check base keys
ALL_KEYS="no_convo_log verify_failed no_training no_nutrition no_weight_data bot_down fitbit_timer_down bf_wrong_source hallucinated_saves incomplete_report empty_dir orphan_openclaw_service stale_memory missing_file git_broken git_uncommitted brief_not_sent brief_no_log disk_high ram_high fitbit_stale fitbit_no_data gog_auth_broken caddy_down caddy_no_response sleep_stale git_remote_behind git_remote_unreachable"
NEVER_FIRED=""
if [ -f "$HITS_FILE" ]; then
    for key in $ALL_KEYS; do
        if ! grep -q "\"key\":\"$key" "$HITS_FILE" 2>/dev/null; then
            NEVER_FIRED="${NEVER_FIRED}\n  - $key"
        fi
    done
fi

# --- 10. Decision log activity ---
DECISIONS_FILE="$REPO_DIR/decisions.log"
DECISIONS_COUNT=0
if [ -f "$DECISIONS_FILE" ]; then
    DECISIONS_COUNT=$(grep -c "^$PREV_MONTH" "$DECISIONS_FILE" 2>/dev/null || true)
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

*Decision Log*
- $DECISIONS_COUNT decisions recorded this month
$([ "$DECISIONS_COUNT" -eq 0 ] && echo "⚠ No decisions logged — are changes being made without recording reasoning?" || echo "- Review: grep '$PREV_MONTH' decisions.log")

*QA Effectiveness Audit*
$(if [ -n "$QA_EFFECTIVENESS" ]; then echo "Checks that fired this month (hits):"; echo "$QA_EFFECTIVENESS"; else echo "No QA hits recorded this month."; fi)
$(if [ -n "$NEVER_FIRED" ]; then printf "Checks that NEVER fired (review if still needed):%b" "$NEVER_FIRED"; else echo "All checks have fired at least once."; fi)

Recommendation notes (review annually):
- 9a (empty\_dir): Low signal — remove if never fires in 3 months
- 9b (orphan\_openclaw): One-time migration check — remove once confirmed clean
- 8b (hallucinated\_saves): Regex-based, false-positive risk — remove if noisy

*Review Checklist*
Reply to discuss any of these:
1. Is architecture.md still coherent?
2. Are we using the best/cheapest tools?
3. Any recurring QA issues to address?
4. Any features to add or remove?
5. Any stale files or procedures?
6. Any QA checks to add, remove, or adjust? (see effectiveness audit above)
EOF
)

# --- Send ---
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d chat_id="${CHAT_ID}" \
    -d parse_mode="Markdown" \
    --data-urlencode "text=${MSG}" > /dev/null

echo "Monthly audit sent for $MONTH"
