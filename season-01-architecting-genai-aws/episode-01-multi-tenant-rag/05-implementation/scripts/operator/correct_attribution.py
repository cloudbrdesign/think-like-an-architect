#!/usr/bin/env python3
"""PRIVILEGED OPERATOR WORKFLOW — correct a misattributed document (CTL-010; ADR-004). Not reachable from any API route.

Ownership is never edited in place. A misattributed document is removed from its current owner's partition, step by
step, with an audit record for every step:

  1. QUARANTINE          status → QUARANTINED (conditional on the current owner)
  2. REMOVE FROM INDEX   DeleteKnowledgeBaseDocuments
  3. DELETE ORIGINAL     DeleteObject
  4. MARK REMOVED        status → REMOVED_FOR_CORRECTION

The document is then uploaded again BY THE CORRECT TENANT'S USER through the normal upload route, so its new owner is
assigned by the trusted ingestion path like every other document. (The document bucket policy lets only the ingestion
service write originals — operators cannot place documents into a tenant's partition directly.)

Usage (operator credentials in the sandbox):
  python3 scripts/operator/correct_attribution.py --variant normal --document-id <id> --target-tenant tenant-b \
      --reason "uploaded by Northwall in error; belongs to Brightmoor"
"""
import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "app"))

import tla_ops  # noqa: E402
from shared import audit, ownership  # noqa: E402
from shared.registry import Registry  # noqa: E402
from shared.tenant_claims import is_tenant_id  # noqa: E402

REMOVED_FOR_CORRECTION = "REMOVED_FOR_CORRECTION"


def correct(sess, outputs, document_id, target_tenant, reason, operator_arn):
    ddb, agent, s3 = sess.client("dynamodb"), sess.client("bedrock-agent"), sess.client("s3")
    registry = Registry(ddb, outputs["RegistryTable"])
    audit_log = audit.AuditLog(ddb, outputs["AuditTable"])
    store = ownership.OwnershipStore(ddb, outputs["RegistryTable"])
    record = registry.get_document(document_id)
    if record is None:
        raise SystemExit(f"REFUSED: document {document_id} not found")
    if record["owner"] == target_tenant:
        raise SystemExit("REFUSED: the document is already owned by the target tenant")
    owner = record["owner"]
    steps = []

    def log(step, outcome):
        entry = audit.new_record(str(uuid.uuid4()), "OPERATOR", "OPERATOR_CORRECTION", None, "operator")
        entry.update(user_id=operator_arn, tenant_context=owner, decision="ALLOW", reason_code="ALLOWED",
                     document_id=document_id, outcome=outcome, correction_step=step,
                     operator_reason=f"{reason} (target tenant {target_tenant})",
                     timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
        audit_log.write_decision(entry)
        steps.append({"step": step, "outcome": outcome, "event_id": entry["event_id"]})

    store.set_status(document_id, owner, ownership.QUARANTINED,
                     (ownership.RECEIVED, ownership.INDEXING, ownership.AVAILABLE, ownership.FAILED))
    log("1-QUARANTINE", "QUARANTINED")
    ownership.delete_from_index(agent, outputs["KnowledgeBaseId"], outputs["DataSourceId"], document_id)
    log("2-REMOVE_FROM_INDEX", "DELETING")
    s3.delete_object(Bucket=outputs["DocumentBucket"], Key=record["s3_key"])
    log("3-DELETE_ORIGINAL", "DELETED")
    store.set_status(document_id, owner, REMOVED_FOR_CORRECTION, (ownership.QUARANTINED,))
    log("4-MARK_REMOVED", REMOVED_FOR_CORRECTION)
    return {"document_id": document_id, "previous_owner": owner, "target_tenant": target_tenant, "steps": steps,
            "next": f"a {target_tenant} user uploads the document again through POST /documents"}


def main():
    parser = argparse.ArgumentParser(description="Privileged, recorded attribution correction")
    parser.add_argument("--variant", choices=("normal",), default="normal")
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--target-tenant", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    if not is_tenant_id(args.target_tenant) or len(args.reason.strip()) < 10:
        raise SystemExit("REFUSED: a valid --target-tenant and a meaningful --reason are required")
    config = tla_ops.load_config()
    sess = tla_ops.session(config)
    account = tla_ops.account_guard(config, sess)
    stack = sess.client("cloudformation").describe_stacks(StackName=tla_ops.names(args.variant, account)["stack"])["Stacks"][0]
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
    operator = sess.client("sts").get_caller_identity()["Arn"]
    print(correct(sess, outputs, args.document_id, args.target_tenant, args.reason, operator))


if __name__ == "__main__":
    main()
