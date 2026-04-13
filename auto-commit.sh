#!/usr/bin/env bash
# Auto-commit any changes in the lifeos repo.
# Runs hourly via cron. Only commits if there are actual changes.
# This captures memory files the bot writes, soul.md edits, etc.
#
# Uses flock against $LOCK so it can't race with bot.py mid-write of memory.md
# or soul.md (which would otherwise stage half-written JSON or markdown).

set -euo pipefail

REPO="/home/openclaw/lifeos"
LOCK="$REPO/.repo.lock"
cd "$REPO"

# Acquire exclusive lock; bail (not error) if another writer holds it.
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "auto-commit: another writer holds $LOCK, skipping this run."
    exit 0
fi

# Dump SQLite to text for diff-friendly git history
DB="$REPO/v2/lifeos.db"
DUMP="$REPO/v2/lifeos.sql"
if [ -f "$DB" ]; then
    sqlite3 "$DB" .dump > "$DUMP" 2>/dev/null || true
fi

# Check if there are any changes (tracked or untracked, excluding gitignored)
if git diff --quiet HEAD && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "No changes to commit."
    exit 0
fi

git add -A
git -c user.email="jarvis@lifeos" -c user.name="J.A.R.V.I.S." commit -m "auto: snapshot $(TZ=America/Toronto date +%Y-%m-%d)"

# Push must fail loudly so cron mail / qa-check sees it. No silent exit 0.
if ! git push origin master 2>&1; then
    echo "auto-commit: push to origin/master FAILED" >&2
    exit 1
fi
echo "Committed and pushed."
