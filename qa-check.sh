#!/bin/bash
# LifeOS v2 — Daily QA integrity check.
# Runs at 8:30am ET via cron. Scans SQLite, services, backups, logs.
# Only sends Telegram alert if unresolved issues found.

set -euo pipefail

LIFEOS_DIR="/home/openclaw/lifeos"
V2_DIR="$LIFEOS_DIR/v2"
DB="$V2_DIR/lifeos.db"
RESOLVED="$LIFEOS_DIR/resolved.jsonl"
QA_HITS="$LIFEOS_DIR/qa-hits.jsonl"
LOG_DIR="$LIFEOS_DIR/logs"
BACKUP_DIR="$V2_DIR/backups"

TODAY=$(TZ="America/Toronto" date +%Y-%m-%d)
YESTERDAY=$(TZ="America/Toronto" date -d "yesterday" +%Y-%m-%d)
DOW=$(TZ="America/Toronto" date +%u)  # 1=Mon, 7=Sun

TELEGRAM_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID_VAL="${CHAT_ID:-}"

FLAGS=()

flag() {
    local key="$1"
    local msg="$2"
    # Log to qa-hits for audit trail
    echo "{\"date\":\"$TODAY\",\"key\":\"$key\",\"msg\":\"$msg\"}" >> "$QA_HITS"
    # Check if resolved
    if [ -f "$RESOLVED" ] && grep -qF "\"$key\"" "$RESOLVED" 2>/dev/null; then
        return
    fi
    FLAGS+=("$msg")
}

# ============================================================
# 1. SQLite DB exists and is readable
# ============================================================
if [ ! -f "$DB" ]; then
    flag "no_db" "SQLite DB not found at $DB"
elif ! sqlite3 "$DB" "SELECT 1" >/dev/null 2>&1; then
    flag "db_corrupt" "SQLite DB failed integrity check"
fi

# ============================================================
# 2. Bot service running
# ============================================================
if ! systemctl is-active --quiet lifeos-bot; then
    flag "bot_down" "lifeos-bot service is not active"
fi

# ============================================================
# 3. Fitbit sync timer active
# ============================================================
if ! systemctl is-active --quiet fitbit-sync.timer 2>/dev/null; then
    flag "fitbit_timer_down" "fitbit-sync.timer is not active"
fi

# ============================================================
# 4. Today's conversation log exists (after 9am)
# ============================================================
HOUR=$(TZ="America/Toronto" date +%H)
if [ "$HOUR" -ge 9 ] && [ ! -f "$LOG_DIR/$TODAY.jsonl" ]; then
    flag "no_log_$TODAY" "No conversation log for today (after 9am)"
fi

# ============================================================
# 5. Yesterday's training logged (except Sundays)
# ============================================================
if [ "$DOW" != "1" ]; then  # Don't check Monday for Sunday training
    TRAIN_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM workout WHERE date='$YESTERDAY'" 2>/dev/null || echo 0)
    if [ "$TRAIN_COUNT" = "0" ]; then
        flag "no_training_$YESTERDAY" "No training logged for $YESTERDAY"
    fi
fi

# ============================================================
# 6. Yesterday's nutrition logged
# ============================================================
NUT_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM nutrition WHERE date='$YESTERDAY'" 2>/dev/null || echo 0)
if [ "$NUT_COUNT" = "0" ]; then
    flag "no_nutrition_$YESTERDAY" "No nutrition logged for $YESTERDAY"
fi

# ============================================================
# 7. Weight logged in last 3 days
# ============================================================
THREE_DAYS_AGO=$(TZ="America/Toronto" date -d "3 days ago" +%Y-%m-%d)
WEIGHT_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM body_metrics WHERE date >= '$THREE_DAYS_AGO'" 2>/dev/null || echo 0)
if [ "$WEIGHT_COUNT" = "0" ]; then
    flag "no_weight_3d" "No weight logged in the last 3 days"
fi

# ============================================================
# 8. Recovery data freshness (< 2 days old)
# ============================================================
REC_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM recovery WHERE date >= '$YESTERDAY'" 2>/dev/null || echo 0)
if [ "$REC_COUNT" = "0" ]; then
    flag "stale_recovery" "No recovery data in last 2 days — Fitbit sync may be failing"
fi

# ============================================================
# 9. Morning brief delivered
# ============================================================
BRIEF_LOG="$LIFEOS_DIR/morning-brief.log"
if [ -f "$BRIEF_LOG" ]; then
    LAST_BRIEF=$(tail -1 "$BRIEF_LOG" 2>/dev/null || echo "")
    if ! echo "$LAST_BRIEF" | grep -q "Morning brief sent"; then
        flag "brief_failed" "Morning brief may have failed (last log line doesn't say 'sent')"
    fi
fi

# ============================================================
# 10. Backup freshness (< 2 hours old)
# ============================================================
if [ -d "$BACKUP_DIR" ]; then
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/lifeos-*.db 2>/dev/null | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        flag "no_backups" "No SQLite backups found"
    else
        BACKUP_AGE=$(( $(date +%s) - $(stat -c %Y "$LATEST_BACKUP") ))
        if [ "$BACKUP_AGE" -gt 7200 ]; then
            flag "stale_backup" "Latest backup is $(( BACKUP_AGE / 3600 ))h old (should be < 2h)"
        fi
    fi
else
    flag "no_backup_dir" "Backup directory not found"
fi

# ============================================================
# 11. Disk space
# ============================================================
DISK_PCT=$(df / --output=pcent | tail -1 | tr -d ' %')
if [ "$DISK_PCT" -gt 85 ]; then
    flag "disk_high" "Disk usage at ${DISK_PCT}% (threshold 85%)"
fi

# ============================================================
# 12. File ownership (must be openclaw, not root)
# ============================================================
ROOT_FILES=$(find "$LIFEOS_DIR" -user root -not -path "*/.git/*" -not -name "*.pyc" 2>/dev/null | head -5)
if [ -n "$ROOT_FILES" ]; then
    flag "root_owned_files" "Root-owned files found: $(echo $ROOT_FILES | head -c 200)"
fi

# ============================================================
# 13. SQLite integrity check (PRAGMA)
# ============================================================
INTEGRITY=$(sqlite3 "$DB" "PRAGMA integrity_check" 2>/dev/null || echo "FAIL")
if [ "$INTEGRITY" != "ok" ]; then
    flag "db_integrity" "SQLite PRAGMA integrity_check failed: $INTEGRITY"
fi

# ============================================================
# 14. Event log health (should have entries from today)
# ============================================================
if [ "$HOUR" -ge 9 ]; then
    EVENT_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM events WHERE ts >= '$TODAY'" 2>/dev/null || echo 0)
    if [ "$EVENT_COUNT" = "0" ]; then
        flag "no_events_today" "No events logged today — bot may not be writing audit trail"
    fi
fi

# ============================================================
# 15. Git repo health (lock + uncommitted changes)
# ============================================================
cd "$LIFEOS_DIR"
if [ -f .git/index.lock ]; then
    sleep 5
    if [ -f .git/index.lock ]; then
        flag "git_lock" "git index.lock still present after 5s wait"
    fi
fi
UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$UNCOMMITTED" -gt 20 ]; then
    flag "git_uncommitted" "$UNCOMMITTED uncommitted changes (auto-commit may be failing)"
fi

# ============================================================
# 16. RAM usage
# ============================================================
MEM_PCT=$(free | awk '/^Mem:/ {printf "%.0f", $3/$2*100}')
if [ "$MEM_PCT" -gt 85 ]; then
    flag "ram_high" "RAM usage at ${MEM_PCT}% (threshold 85%)"
fi

# ============================================================
# 17. Tool verification failures in today's log
# ============================================================
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    TOOL_FAILS=$(grep -c '"FAILED\|"ERROR\|"error' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null || echo 0)
    if [ "$TOOL_FAILS" -gt 0 ]; then
        flag "tool_failures_$TODAY" "$TOOL_FAILS tool error(s) in today's conversation log"
    fi
fi

# ============================================================
# 18. Silent tool errors (errors in log but no user-facing mention)
# ============================================================
if [ -f "$LOG_DIR/$TODAY.jsonl" ]; then
    # Count tool errors vs error mentions in assistant replies
    TOOL_ERRORS=$(grep -o '"result":[^}]*\(ERROR\|FAILED\|error\|failed\)' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l || echo 0)
    ERROR_MENTIONS=$(grep -o '"assistant":[^}]*\(error\|fail\|could not\|unable\)' "$LOG_DIR/$TODAY.jsonl" 2>/dev/null | wc -l || echo 0)
    if [ "$TOOL_ERRORS" -gt 0 ] && [ "$ERROR_MENTIONS" = "0" ]; then
        flag "silent_tool_errors_$TODAY" "$TOOL_ERRORS tool errors today but none surfaced to user"
    fi
fi

# ============================================================
# 19. Stale memory files (>30d, not referenced in recent logs)
# ============================================================
MEMORY_DIR="$LIFEOS_DIR/memory"
if [ -d "$MEMORY_DIR" ]; then
    find "$MEMORY_DIR" -name "*.md" -mtime +30 -type f 2>/dev/null | while read -r mf; do
        fname=$(basename "$mf")
        # Check if any log in last 7 days references this file
        RECENT_REF=$(grep -rl "$fname" "$LOG_DIR"/ 2>/dev/null | head -1)
        if [ -z "$RECENT_REF" ]; then
            flag "stale_memory_$fname" "memory/$fname not modified in 30+ days and not referenced in recent logs"
        fi
    done
fi

# ============================================================
# 20. Caddy web server health
# ============================================================
if systemctl is-active --quiet caddy 2>/dev/null; then
    CADDY_RESP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost/ 2>/dev/null || echo "000")
    if [ "$CADDY_RESP" = "000" ]; then
        flag "caddy_no_response" "Caddy running but not responding on localhost"
    fi
elif systemctl list-unit-files caddy.service >/dev/null 2>&1; then
    flag "caddy_down" "Caddy service is not running"
fi

# ============================================================
# 21. Git remote reachable + up to date
# ============================================================
if git remote get-url origin >/dev/null 2>&1; then
    if ! git ls-remote --exit-code origin HEAD >/dev/null 2>&1; then
        flag "git_remote_unreachable" "Cannot reach git remote — backup is not updating"
    else
        LOCAL_SHA=$(git rev-parse HEAD 2>/dev/null)
        REMOTE_SHA=$(git ls-remote origin HEAD 2>/dev/null | awk '{print $1}')
        if [ -n "$LOCAL_SHA" ] && [ -n "$REMOTE_SHA" ] && [ "$LOCAL_SHA" != "$REMOTE_SHA" ]; then
            flag "git_remote_behind" "Git remote differs from local HEAD — pushes may be failing"
        fi
    fi
fi

# ============================================================
# 22. Stale soul proposals (>5 pending)
# ============================================================
PROPOSALS="$LIFEOS_DIR/soul-proposals.jsonl"
if [ -f "$PROPOSALS" ]; then
    PENDING=$(grep -c '"status": "pending"' "$PROPOSALS" 2>/dev/null || echo 0)
    if [ "$PENDING" -gt 5 ]; then
        flag "stale_soul_proposals" "$PENDING pending soul proposals — review may not be running"
    fi
fi

# ============================================================
# 23. Architecture drift (missing expected files)
# ============================================================
for f in bot.py soul.md architecture.md auto-commit.sh qa-check.sh v2/schema.sql v2/router.py v2/lifeos_cli.py; do
    if [ ! -f "$LIFEOS_DIR/$f" ]; then
        flag "missing_file_$f" "Missing expected file: $f"
    fi
done

# ============================================================
# Send alert if any unresolved flags
# ============================================================
if [ ${#FLAGS[@]} -gt 0 ]; then
    MSG="QA Check ($TODAY) — ${#FLAGS[@]} issue(s):"
    for f in "${FLAGS[@]}"; do
        MSG="$MSG
- $f"
    done
    if [ -n "$TELEGRAM_TOKEN" ] && [ -n "$CHAT_ID_VAL" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
            -d "chat_id=${CHAT_ID_VAL}" \
            -d "text=${MSG}" >/dev/null 2>&1 || true
    fi
    echo "$MSG"
else
    echo "QA Check ($TODAY): all clear"
fi
