#!/usr/bin/env bash
# Step 2 — deploy the stack (normal). The sensitivity variant is deployed only by sensitivity-run.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/tla_ops.py deploy "${1:-normal}"
