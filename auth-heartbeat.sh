#!/usr/bin/env bash
# Hourly Google Sheets auth heartbeat.
# qa-check.sh Check 16 catches gog auth failure but only runs once a day at 8:30am ET.
# This runs hourly so a revoked OAuth2 token gets caught within an hour, not 24.
# Pings Telegram immediately on failure.

set -euo pipefail

source /opt/openclaw.env
BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
CHAT_ID="${CHAT_ID}"
GOG="${GOG_PATH:-/usr/local/bin/gog}"
GOG_ACCT="${GOG_ACCOUNT}"
SHEET_ID="${SHEET_ID}"
STATE_FILE="/home/openclaw/lifeos/.auth-heartbeat.state"

export HOME=/home/openclaw
export GOG_KEYRING_PASSWORD="${GOG_KEYRING_PASSWORD:-}"

# One-shot sheet read. If this works, auth is alive.
RESULT=$("$GOG" sheets get "$SHEET_ID" "Body Metrics!A1:A1" --account "$GOG_ACCT" --no-input 2>&1 || true)

# Use a state file so we only alert on transitions (good→bad), not every hour.
PREV_STATE="ok"
[ -f "$STATE_FILE" ] && PREV_STATE=$(cat "$STATE_FILE")

if echo "$RESULT" | grep -qiE "invalid_grant|token has been expired|token has been revoked|oauth2:"; then
    echo "bad" > "$STATE_FILE"
    if [ "$PREV_STATE" = "ok" ]; then
        # Transition: just broke. Alert immediately.
        MSG=$(printf "*🔑 Google Sheets auth FAILED*\\n\\nThe gog OAuth2 token is expired or revoked. The bot can't read or write sheets until reauth.\\n\\nFix: ask Claude Code to run \\\`gog login\\\` and follow the playbook (audit-playbook.md → Common traps).\\n\\nError: %s" "$(echo "$RESULT" | head -1)")
        curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
            -d chat_id="${CHAT_ID}" \
            -d parse_mode="Markdown" \
            --data-urlencode "text=${MSG}" > /dev/null
        echo "auth-heartbeat: ALERT sent (token broke)"
    else
        echo "auth-heartbeat: still broken (no re-alert)"
    fi
    exit 1
fi

# Auth works.
echo "ok" > "$STATE_FILE"
if [ "$PREV_STATE" = "bad" ]; then
    # Transition: just recovered. Confirm.
    MSG="*🔑 Google Sheets auth RESTORED*"$'\n\n'"Token works again. Bot can read/write sheets normally."
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="${CHAT_ID}" \
        -d parse_mode="Markdown" \
        --data-urlencode "text=${MSG}" > /dev/null
    echo "auth-heartbeat: RECOVERY sent"
fi
echo "auth-heartbeat: ok"
