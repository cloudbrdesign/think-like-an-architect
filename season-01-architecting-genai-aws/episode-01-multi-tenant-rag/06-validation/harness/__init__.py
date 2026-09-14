"""Validation harness for the Episode 01 learner implementation. Runs on the learner's machine; never deployed.

    python3 -m harness fixtures load
    python3 -m harness identity show --as user-a
    python3 -m harness ask --as user-a --forge tenant-b "What weekend call-out rate does Brightmoor charge?"
    python3 -m harness inspect event <event_id>
    python3 -m harness run --suite all
    python3 -m harness verify-cleanup
    python3 -m harness evidence bundle --run-id <run-id> --out <folder>

Exit codes: 0 all PASS or NOT_APPLICABLE · 1 any FAIL · 2 any ERROR · 3 target guard refused.
"""
