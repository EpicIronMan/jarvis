#!/bin/bash
# LifeOS v2 — Hourly SQLite backup with retention ladder.
# 48h hourly snapshots, 30d daily, 12m monthly.
#
# Usage: /home/openclaw/lifeos/v2/backup.sh

set -euo pipefail

DB="/home/openclaw/lifeos/v2/lifeos.db"
BACKUP_DIR="/home/openclaw/lifeos/v2/backups"
DUMP_FILE="/home/openclaw/lifeos/v2/lifeos.sql"

mkdir -p "$BACKUP_DIR"

# 1. Create hourly snapshot
TS=$(date +"%Y-%m-%d_%H%M")
cp "$DB" "$BACKUP_DIR/lifeos-${TS}.db"

# 2. Create text dump for git (diff-friendly)
sqlite3 "$DB" .dump > "$DUMP_FILE"

# 3. Retention cleanup
NOW=$(date +%s)

# Delete hourly backups older than 48h
find "$BACKUP_DIR" -name "lifeos-*.db" -type f | while read -r f; do
    AGE=$(( NOW - $(stat -c %Y "$f") ))
    if [ $AGE -gt 172800 ]; then
        # Keep if it's a daily (noon) or monthly (1st of month) snapshot
        FNAME=$(basename "$f")
        HOUR=$(echo "$FNAME" | grep -oP '\d{4}-\d{2}-\d{2}_\K\d{2}')
        DAY=$(echo "$FNAME" | grep -oP '\d{4}-\d{2}-\K\d{2}')
        if [ "$HOUR" = "12" ]; then
            # Keep daily (noon) snapshots for 30 days
            if [ $AGE -gt 2592000 ]; then
                if [ "$DAY" = "01" ]; then
                    # Keep monthly (1st) snapshots for 12 months
                    if [ $AGE -gt 31536000 ]; then
                        rm -f "$f"
                    fi
                else
                    rm -f "$f"
                fi
            fi
        else
            rm -f "$f"
        fi
    fi
done

echo "Backup complete: lifeos-${TS}.db"
