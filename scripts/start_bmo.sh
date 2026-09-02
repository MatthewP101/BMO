#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
    echo "Create the environment first: python3 -m venv .venv"
    exit 1
fi
exec .venv/bin/python -m app.main
