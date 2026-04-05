#!/usr/bin/env bash
# Auto-commit any changes in the lifeos repo.
# Runs daily via cron. Only commits if there are actual changes.
# This captures memory files the bot writes, soul.md edits, etc.

set -euo pipefail

REPO="/home/openclaw/lifeos"
cd "$REPO"

# Check if there are any changes (tracked or untracked, excluding gitignored)
if git diff --quiet HEAD && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "No changes to commit."
    exit 0
fi

git add -A
git -c user.email="jarvis@lifeos" -c user.name="J.A.R.V.I.S." commit -m "auto: snapshot $(TZ=America/Toronto date +%Y-%m-%d)"
echo "Committed changes."
