#!/usr/bin/env bash
# Nxance MBP — zero-spend launcher
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
echo ""
echo "  Nxance MBP (₹0 infra)"
echo "  Open http://127.0.0.1:8000"
echo "  Unlock test codes: DEMO-UNLOCK | NXANCE-TEST"
echo ""
exec python3 -m app.main
