# Build It — The Veltamere Document Assistant

This folder is the **educational implementation** of the architecture you designed and defended in this episode.

```
IDENTITY → AUTHENTICATION → TRUSTED TENANT CONTEXT → TENANT REGISTRY CHECK → AUTHORITATIVE RETRIEVAL GATEWAY
→ MANDATORY TENANT FILTER → RETRIEVAL → OWNERSHIP VERIFICATION → CITATION ALLOW-LIST → GENERATION → AUDIT EVIDENCE
```

You will deploy it into **your own sandbox AWS account**, attack it, prove the tenant boundary holds, prove the tests
can fail, and clean everything up. It is small on purpose: the security-relevant code is meant to be read.

> Deploying creates billable resources. Read [COST_AND_CLEANUP.md](COST_AND_CLEANUP.md) first, and plan to deploy,
> validate and clean up in one session.

## Answer these from the repository

| Question | Where the answer is |
|---|---|
| **Where does tenant authority come from?** | [`app/shared/tenant_context.py`](app/shared/tenant_context.py) — only verified token claims plus the registry. [`app/shared/tenant_claims.py`](app/shared/tenant_claims.py) turns the group claim into exactly one tenant, or denies. |
| **Where is authorisation enforced?** | [`app/shared/retrieval_scope.py`](app/shared/retrieval_scope.py) `authorize_and_scope()` — the decision and the constraint in one code path. |
| **Where is the retrieval filter built?** | The same file, `build_tenant_filter()`: `{"equals": {"key": "owning_tenant", "value": <tenant>}}`. It is the only place the constraint exists. [`app/shared/retrieval_client.py`](app/shared/retrieval_client.py) can only send what that function issued. |
| **What prevents bypass?** | [`infrastructure/template.yaml`](infrastructure/template.yaml): only the query role may `Retrieve`; only the ingestion role may index; each function may be invoked only by the API (explicit Deny for everyone else); the document bucket refuses other readers and writers. |
| **What happens if retrieval returns the wrong owner?** | [`app/shared/ownership_verification.py`](app/shared/ownership_verification.py) — defence in depth: any mismatch withholds the whole response (`OWNERSHIP_MISMATCH`), before anything reaches the model. |
| **How do we know the test is not vacuous?** | [`../06-validation/harness/suites/isolation.py`](../06-validation/harness/suites/isolation.py) checks that the other tenant's document exists and ranks for the same question first, and [`scripts/sensitivity-run.sh`](scripts/sensitivity-run.sh) removes the primary control in a separate deployment to show the tests then fail. |

## What is in this folder

```
infrastructure/template.yaml   every resource and every IAM permission (one CloudFormation stack)
app/shared/                    trust transition, primary control, verification, citations, audit, reason codes
app/query/handler.py           POST /ask — the principle chain in order, failing closed at every step
app/ingestion/handler.py       POST /documents · GET/DELETE /documents/{id} — ownership from the trusted context
scripts/                       preflight · build · deploy · sensitivity-run · cleanup (+ tla_ops.py they call)
scripts/operator/              privileged, recorded attribution-correction workflow (not reachable from the API)
config/learner.env.example     your region, profile and expected account — no secrets
../06-validation/harness/      the test harness (runs on your machine, never deployed)
../06-validation/tests/        component tests of app/shared (standard library only)
../06-validation/fixtures/     synthetic tenants, users and documents with canary markers
../06-validation/sensitivity/  the TEST-ONLY replacement of retrieval_scope.py
```

## Prerequisites

- A **dedicated sandbox AWS account** with administrator credentials in it (see
  [PLATFORM_VERIFICATION section 1](PLATFORM_VERIFICATION.md#1-learner-sandbox-requirements-pd-09)).
- Region **us-east-1**. Amazon Titan Text Embeddings V2 and Amazon Nova Micro must be usable In-Region; preflight
  checks this and tells you if the account needs model access enabled once.
- Python 3.10+ with `boto3` (`python3 -m pip install boto3`). Nothing else.
- Recommended: an AWS Budgets alert (for example USD 20 with alerts at 50/80/100%).

```
cp config/learner.env.example config/learner.env    # set AWS_PROFILE, AWS_REGION, TLA_EXPECTED_ACCOUNT
```

If you deploy with a restricted deployment role instead of an administrator, set `TLA_ROLE_PATH` and
`TLA_PERMISSIONS_BOUNDARY_ARN` to what that role requires. (CloudBrewery's own validation role also needs one narrowly
scoped `apigateway:TagResource` compatibility permission for tagged API stage creation; administrators already have it.)

## Run it — steps 0 to 6

Run from this folder (`05-implementation/`) unless noted. Every step is non-interactive.

| Step | Command | What you should see |
|---|---|---|
| 0 | `scripts/preflight.sh` | Account, region, both models `AUTHORIZED/AVAILABLE`, model invocation logging disabled, `preflight: PASS` |
| 1 | `scripts/build.sh normal` | Two deterministic packages with SHA-256 hashes. The normal build refuses any sensitivity-variant code |
| 2 | `scripts/deploy.sh` | Stack `tla-s01e01-normal` `CREATE_COMPLETE` and the API endpoint |
| 3 | `cd ../06-validation && python3 -m harness fixtures load` | Tenants A and B, test users, and 7 documents uploaded **through the API as each tenant's user**, all `AVAILABLE` |
| 4 | `python3 -m harness run --suite all` | Every test with PASS / FAIL / ERROR / NOT_RUN / NOT_APPLICABLE, and `results/<run-id>/summary.md` |
| 5 | `cd ../05-implementation && scripts/sensitivity-run.sh` | Normal PASS → sensitivity variant **FAIL** (as intended) → variant destroyed → normal PASS → `TST-SEN-011 PASS` |
| 6 | `python3 -m harness evidence bundle --run-id <id> --out ~/tla-evidence` then `scripts/cleanup.sh` then `cd ../06-validation && python3 -m harness verify-cleanup` | Your evidence copied, every lab resource deleted, `TST-OPS-012 PASS — CLEAN` |

The full suite takes about 20–30 minutes, mostly waiting for documents to index and for one test token to expire.

## Explore the boundary yourself (between steps 3 and 4)

```
cd ../06-validation
python3 -m harness identity show --as user-a              # verified claims; the token itself is never printed
python3 -m harness ask --as user-a "What is the weekend call-out rate in our cleaning services contract?"
python3 -m harness ask --as user-a --forge tenant-b "What weekend call-out rate does Brightmoor Services charge?"
python3 -m harness inspect event <event_id>               # who, which tenant, constraint, retrieved — no content
```

With `--forge`, `tenant-b` is sent in the query string, a header and the question text. The audit record still shows
`tenant_context: tenant-a` and `constraint.value: tenant-a`, and no Brightmoor document appears in `retrieved`. A
`tenant_id` field in the request body is refused outright with `REQUEST_FIELD_REJECTED`.

## The sensitivity test is a separate build, never a switch

There is no flag, parameter or environment variable that weakens the tenant constraint. `scripts/build.sh sensitivity`
copies [`../06-validation/sensitivity/retrieval_scope.py`](../06-validation/sensitivity/retrieval_scope.py) over the
primary control **in a separate build folder**, and `sensitivity-run.sh` deploys it as its own stack
(`tla-s01e01-sensitivity`, tag `Variant=sensitivity`), runs only the cross-tenant tests against it, and always destroys
it. The harness refuses to run normal suites against that stack, and the sensitivity suite against the normal one.

## Clean up

`scripts/cleanup.sh` deletes the sensitivity stack (if present), empties the document bucket, deletes the stack, and
empties and deletes the artifact bucket. `python3 -m harness verify-cleanup` then checks every service directly.
A tag search can still list a resource for a while after it is deleted, so each tagged resource is confirmed with its
own service before it counts as remaining.

## Teaching simplifications

The simplifications in [IMPLEMENTATION_DESIGN section 13](IMPLEMENTATION_DESIGN.md#13-teaching-simplifications) apply:
administrator-initiated test sign-in, audit table in the same stack, 1-day logs, no WAF or quotas, and your sandbox
administrator acting as deployer and operator. None of them removes a taught control.

## Evidence for your portfolio

Keep `results.json`, `summary.md` and the `evidence/` folder from your run, the sensitivity verdict, and the clean
`verify-cleanup` result. Account numbers are already redacted. This is **portfolio evidence of the work you performed —
not certification**.
