#!/usr/bin/env bash
# Step 0 — read-only checks: account, region, In-Region model access (VE-18), model invocation logging (CTL-024).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/tla_ops.py preflight "$@"
