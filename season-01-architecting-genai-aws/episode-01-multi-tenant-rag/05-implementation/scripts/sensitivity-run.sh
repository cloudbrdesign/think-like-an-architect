#!/usr/bin/env bash
# Step 5 — TST-SEN-011: prove the isolation tests detect removal of the primary control (CTL-015).
#   normal ISO-003/004 PASS → build + deploy the sensitivity variant → ISO-003/004 expected FAIL
#   → destroy the variant (always, even after an error) → verify → normal ISO-003/004 PASS again → verdict
# Requires the normal deployment with fixtures loaded. Synthetic data only.
set -uo pipefail
IMPL="$(cd "$(dirname "$0")/.." && pwd)"
VALIDATION="$(cd "$IMPL/../06-validation" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
harness() { (cd "$VALIDATION" && python3 -m harness "$@"); }
destroy_variant() {
  echo "== destroying the sensitivity variant"
  (cd "$IMPL" && python3 scripts/tla_ops.py cleanup --variant sensitivity)
  harness verify-cleanup --variant sensitivity --run-id "sen-$STAMP-cleanup"
}
trap destroy_variant EXIT

echo "== 1/5 baseline: normal deployment"
harness run --variant normal --suite isolation-negative --run-id "sen-$STAMP-baseline"
echo "== 2/5 build and deploy the sensitivity variant"
(cd "$IMPL" && python3 scripts/tla_ops.py build sensitivity) || exit 1
(cd "$IMPL" && TLA_SENSITIVITY_RUN=1 python3 scripts/tla_ops.py deploy sensitivity) || exit 1
harness fixtures load --variant sensitivity --set ab || exit 1
echo "== 3/5 isolation tests against the sensitivity variant (expected to FAIL)"
harness run --variant sensitivity --suite sensitivity --run-id "sen-$STAMP-variant"
echo "== 4/5 destroy the variant"
trap - EXIT
destroy_variant
echo "== 5/5 bracketing: normal deployment again"
harness run --variant normal --suite isolation-negative --run-id "sen-$STAMP-bracket"
harness sensitivity-verdict --stamp "sen-$STAMP"
