#!/usr/bin/env bash
# Step 6 — delete everything this lab created (sensitivity stack first), then run: python3 -m harness verify-cleanup
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/tla_ops.py cleanup "$@"
