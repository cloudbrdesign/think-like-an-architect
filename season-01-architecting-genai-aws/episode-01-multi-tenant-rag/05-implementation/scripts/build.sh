#!/usr/bin/env bash
# Step 1 — package the functions. Usage: scripts/build.sh normal | sensitivity
# The normal build refuses to contain anything from 06-validation/sensitivity/.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/tla_ops.py build "${1:?usage: build.sh normal|sensitivity}"
