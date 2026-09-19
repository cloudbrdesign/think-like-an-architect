"""The change path: notifier · applier · reconciler · rebuild (ADR-003 … ADR-006, ADR-008).

Three responsibilities, deliberately not collapsed into one component:

    PROTECT THE REQUEST   query/handler.py + core/verification.py   (authority at answer time)
    PROVE CONVERGENCE     change/notifier.py + change/reconciler.py (delivery for latency, reconciliation for proof)
    REBUILD WHEN NEEDED   change/rebuild.py                          (build, verify, promote, retire)

The applier is the only component that writes derived retrieval state, and it applies every change — notified, repaired
or rebuilt — through the same ordered, idempotent path (ADR-004).
"""
