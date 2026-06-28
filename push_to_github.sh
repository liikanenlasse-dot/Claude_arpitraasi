#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/liikanenlasse-dot/Claude_arpitraasi.git"
REPO_DIR="Claude_arpitraasi"

if ! command -v git >/dev/null 2>&1; then
  echo "Git is not installed or not available in PATH." >&2
  exit 1
fi

if [ ! -d "$REPO_DIR" ]; then
  git clone "$REPO_URL" "$REPO_DIR"
fi

rsync -av --exclude "$REPO_DIR" --exclude ".git" --exclude "*.zip" ./ "$REPO_DIR"/
cd "$REPO_DIR"

git add .
git status

git commit -m "Initial Veikkaus odds monitor"
git push origin main

echo "Done. Open: https://github.com/liikanenlasse-dot/Claude_arpitraasi"
