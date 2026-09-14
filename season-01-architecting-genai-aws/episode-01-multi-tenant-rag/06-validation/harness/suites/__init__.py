"""Suites, in the execution order of TEST_HARNESS_DESIGN section 8. `run --suite all` runs ORDER."""
from harness.suites import audit, identity, ingestion, isolation, lifecycle, onboarding, permissions, redteam, security
from harness.suites import sensitivity

SUITES = {
    "permissions": permissions.run,
    "identity": identity.run,
    "isolation": isolation.run,
    "isolation-negative": isolation.run_negative,
    "security": security.run,
    "ingestion": ingestion.run,
    "audit": audit.run,
    "onboarding": onboarding.run,
    "lifecycle": lifecycle.run,
    "identity-expiry": identity.run_expiry,
    "redteam": redteam.run,
    "sensitivity": sensitivity.run,
}
ORDER = ["permissions", "identity", "isolation", "security", "ingestion", "audit", "onboarding", "lifecycle",
         "identity-expiry", "redteam"]
