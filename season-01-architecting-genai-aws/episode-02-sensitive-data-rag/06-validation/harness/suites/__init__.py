"""The 31 validation tests (VALIDATION_PLAN §3). Each test function returns (passed, observed, evidence); the runner
records PASS / FAIL, or ERROR if the test itself could not complete. Nothing is pre-filled."""
import traceback

REGISTRY = {}


def test(test_id, category, verifies, controls, level, expected):
    def register(function):
        REGISTRY[test_id] = {"function": function, "category": category, "verifies": verifies, "controls": controls,
                             "level": level, "expected": expected}
        return function
    return register


# Order matters: tests that inject faults restore state; the whole-run scans and the expired-token test come last.
ORDER = ["TST-ELG-001", "TST-ELG-002", "TST-ELG-003", "TST-ELG-004", "TST-ELG-005", "TST-ELG-006", "TST-ELG-007",
         "TST-ELG-008", "TST-ELG-009", "TST-SEC-002", "TST-SEC-003", "TST-SEC-006", "TST-DATA-001", "TST-DATA-002",
         "TST-DATA-003", "TST-DATA-004", "TST-DATA-005", "TST-DATA-006", "TST-SCALE-001", "TST-SEC-004",
         "TST-CHG-001", "TST-SEC-007", "TST-CHG-002", "TST-SEC-005", "TST-OBS-002", "TST-OBS-001", "TST-SEC-001"]
RUNBOOK_TESTS = ["TST-OPS-001", "TST-SEN-001", "TST-SEN-002", "TST-SEN-003"]      # recorded by the runbook
EXPERIMENT_TARGETS = {1: ["TST-ELG-003", "TST-ELG-005", "TST-ELG-006", "TST-ELG-009"],
                      2: ["TST-ELG-004", "TST-DATA-005", "TST-DATA-006"],
                      3: ["TST-CHG-001"]}


def load_all():
    from harness.suites import change, data, eligibility, observability, security  # noqa: F401


def run_tests(ctx, test_ids):
    load_all()
    exit_code = 0
    for test_id in [t for t in ORDER if t in test_ids]:
        spec = REGISTRY[test_id]
        try:
            passed, observed, evidence = spec["function"](ctx)
            status = "PASS" if passed else "FAIL"
        except Exception as error:  # noqa: BLE001 — a crashed test is an ERROR, never silently skipped
            status, observed = "ERROR", f"{type(error).__name__}: {error}"
            evidence = {"traceback": traceback.format_exc()[-3000:]}
        ctx.run.record(test_id, spec["category"], spec["verifies"], spec["controls"], spec["level"], spec["expected"],
                       status, observed, evidence)
        exit_code |= status != "PASS"
    return exit_code
