#!/usr/bin/env bash
# J.A.R.V.I.S. Morning Brief — daily Telegram message at 7am ET
# Cron: 0 7 * * * (America/Toronto)

set -euo pipefail

# --- Config (all from env file — no personal info in code) ---
source /opt/openclaw.env
BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
CHAT_ID="${CHAT_ID}"
GOG_BIN="${GOG_PATH:-/usr/local/bin/gog}"

# --- Guard: only send once per day ---
TODAY=$(TZ=America/Toronto date +%Y-%m-%d)
LOCK_FILE="/tmp/morning-brief-${TODAY}.sent"

if [ -f "$LOCK_FILE" ]; then
  echo "Morning brief already sent today ($TODAY). Skipping."
  exit 0
fi

# --- Determine today's workout ---
DOW=$(TZ=America/Toronto date +%A)
case "$DOW" in
  Monday|Thursday)
    WORKOUT="*Back \& Arms* — Pull Ups, Lat Pull Downs, Seated Cable Rows, Reverse Pec Fly, Preacher Curls (3x8)"
    ;;
  Tuesday|Friday)
    WORKOUT="*Chest \& Shoulders* — Incline Bench Press, Single Arm Cable Raise, Cable Flies, Shoulder Press (3x8)"
    ;;
  Wednesday|Saturday)
    WORKOUT="*Legs \& Abs* — Leg Press, Leg Curls, Leg Extensions, Weighted Captain Chair (3x8)"
    ;;
  Sunday)
    WORKOUT="*Rest Day* — recover, stretch, walk."
    ;;
esac

# --- Motivational one-liners (rotate by day of year) ---
QUOTES=(
  "Discipline is choosing between what you want now and what you want most."
  "You don't have to be extreme, just consistent."
  "The body achieves what the mind believes."
  "Small daily improvements are the key to staggering long-term results."
  "Suffer the pain of discipline or suffer the pain of regret."
  "You're not tired, you're uninspired. Lock in."
  "The deficit is temporary. The physique is permanent."
  "Trust the process. The mirror will catch up to the scale."
  "Every rep is a vote for the person you're becoming."
  "1000 cal deficit is aggressive. That's the point."
  "You didn't come this far to only come this far."
  "Your body is an experiment. Run it like a scientist."
  "Consistency over intensity. Show up."
  "The cut ends. The habits don't."
)
DOY=$(TZ=America/Toronto date +%j)
QUOTE="${QUOTES[$((10#$DOY % ${#QUOTES[@]}))]}"

# --- Pull latest weight from Google Sheet ---
LATEST_ROW=$(HOME=/home/openclaw \
  "$GOG_BIN" sheets get "$SHEET_ID" "Body Metrics!A:B" --account "$GOG_ACCOUNT" --no-input 2>/dev/null \
  | tail -1)
LATEST_WEIGHT_DATE=$(echo "$LATEST_ROW" | awk '{print $1}')
LATEST_WEIGHT=$(echo "$LATEST_ROW" | awk '{print $2}')

if [ -z "$LATEST_WEIGHT" ] || [ "$LATEST_WEIGHT" = "Weight" ]; then
  WEIGHT_LINE="Weight: target range (no recent weigh-in)"
else
  WEIGHT_LINE="Weight: ${LATEST_WEIGHT} lbs (${LATEST_WEIGHT_DATE})"
fi

# --- Build message ---
MSG=$(cat <<EOF
*J.A.R.V.I.S. Morning Brief — ${DOW}, ${TODAY}*

*Today's Workout*
${WORKOUT}

*Goals Snapshot*
- BF: Check latest DEXA
- ${WEIGHT_LINE}
- Deficit: 1000 cal/day
- Strength: no >5% decline in 2-week rolling avg

_${QUOTE}_
EOF
)

# --- Send via Telegram Bot API ---
RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d parse_mode="Markdown" \
  --data-urlencode "text=${MSG}")

OK=$(echo "$RESPONSE" | jq -r '.ok' 2>/dev/null || echo "false")
if [ "$OK" = "true" ]; then
  echo "Morning brief sent successfully."
  touch "$LOCK_FILE"
else
  echo "Failed to send morning brief: $RESPONSE" >&2
  exit 1
fi
