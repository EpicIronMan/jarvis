#!/usr/bin/env bash
# Mark a QA issue as resolved.
# Usage: ./resolve.sh <issue_key> "description of what fixed it"
# Example: ./resolve.sh fitbit_timer_down "Restarted fitbit-sync.timer"
#
# The QA script checks resolved.jsonl before alerting.
# If an issue reappears after being resolved, it means the fix didn't hold —
# remove the resolved entry to re-enable alerting.

set -euo pipefail

RESOLVED_FILE="/home/openclaw/lifeos/resolved.jsonl"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <issue_key> \"fix description\""
    echo ""
    echo "Current resolved issues:"
    if [ -f "$RESOLVED_FILE" ] && [ -s "$RESOLVED_FILE" ]; then
        cat "$RESOLVED_FILE"
    else
        echo "  (none)"
    fi
    exit 1
fi

KEY="$1"
FIX="$2"
DATE=$(TZ=America/Toronto date +%Y-%m-%d)

echo "{\"key\":\"$KEY\",\"fix\":\"$FIX\",\"date\":\"$DATE\"}" >> "$RESOLVED_FILE"
echo "Resolved: $KEY — $FIX ($DATE)"
