#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x .venv/bin/python ]]; then
  echo "Run scripts/run_local.sh once to install the project first."
  exit 1
fi

.venv/bin/python -m fpl_mvp all --force-refresh
echo "FPL data, xP recommendations, briefing, and the static site are up to date."

