"""Fixture loader (B11, TS-E02-03). PRIVILEGED: the sandbox operator writes the simulated authoritative systems.

  * records system:        fixtures/records/D-NN.md → records bucket
  * classification store:  one item per document (current) + HISTORY#<document>#v<version> items for reconstruction
  * identities:            one Cognito user per persona; token groups mirror grants ONLY where the fixture says so
  * grants store:          HR and GRANTS records keyed by the identity subject, + HR#v… / GRANTS#v… history items
                           (P-09 gets an identity and no records)
  * ingestion:             the deployed ingestion job is invoked for every document
"""
import json
import os

from harness import canaries
from adapters.stores import to_item


def put_classification(ddb, table, record):
    body = json.dumps(record, sort_keys=True)
    ddb.put_item(TableName=table, Item=to_item({"document_id": record["document_id"], "version": record["version"],
                                                "record": body}))
    ddb.put_item(TableName=table, Item=to_item({"document_id": f"HISTORY#{record['document_id']}#v{record['version']}",
                                                "version": record["version"], "record": body}))


def put_grants(ddb, table, subject, persona, domains=None, cases=None, grants_version=None, status=None,
               hr_version=None):
    hr = {"requester_sub": subject, "record": "HR", "employee_id": persona["employee_id"],
          "employment_status": status or persona["employment_status"], "hr_version": hr_version or persona["hr_version"]}
    grants = {"requester_sub": subject, "record": "GRANTS",
              "domains": list(persona["domains"] if domains is None else domains),
              "cases": list(persona["cases"] if cases is None else cases),
              "grants_version": grants_version or persona["grants_version"]}
    for item in (hr, grants):
        ddb.put_item(TableName=table, Item=to_item(item))
        history = dict(item, record=f"{item['record']}#v{item['hr_version' if item['record'] == 'HR' else 'grants_version']}")
        ddb.put_item(TableName=table, Item=to_item(history))


def invoke_ingestion(target, document_ids):
    response = target.client("lambda", read_timeout=320, retries={"max_attempts": 0}).invoke(
        FunctionName=target.outputs["IngestionFunctionName"], InvocationType="RequestResponse",
        Payload=json.dumps({"document_ids": document_ids}).encode())
    payload = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise RuntimeError(f"ingestion failed: {payload.get('errorType')}: {str(payload.get('errorMessage'))[:300]}")
    return payload


def load(target, identities):
    s3, ddb = target.client("s3"), target.client("dynamodb")
    records = canaries.records()
    for document_id in sorted(records):
        s3.put_object(Bucket=target.outputs["RecordsBucket"], Key=f"records/{document_id}.md",
                      Body=canaries.markdown(document_id).encode(), ContentType="text/markdown; charset=utf-8")
        put_classification(ddb, target.outputs["ClassificationTable"], records[document_id])
    subjects = {}
    for name, persona in sorted(canaries.personas().items()):
        subject = identities.ensure_user(persona["username"], identities.group_names(persona))
        subjects[name] = subject
        if persona["registered"]:
            put_grants(ddb, target.outputs["AuthorizationTable"], subject, persona)
    report = invoke_ingestion(target, sorted(records))
    return {"documents": len(records), "personas": len(subjects),
            "objects": {tier: len(ids) for tier, ids in report["objects"].items()},
            "quarantine": report["quarantine"], "special_category_excluded": report["special_category_excluded"],
            "index_status": report["index_status"]}


def subjects(identities):
    return {name: identities.subject(p["username"]) for name, p in canaries.personas().items()}


def results_path(*parts):
    return os.path.join(canaries.common.RESULTS, *parts)
