# Educational implementation — Kestrelmoor Knowledge Assistant

This folder is the working implementation of the architecture in `../03-architecture/` and `../04-decisions/`. It
exists to let you **see and test** one invariant:

> A section reaches generation only if its owner-assigned classification and scope, as currently recorded, match an
> entitlement the requester holds at the moment of the request — decided outside the model, enforced inside the
> search, re-checked before generation. Content that no use case needs is never indexed.

- **Authenticated is not authorised.**
- **Authorised for a document is not authorised for every section.**
- **The model is not the authorization authority. The prompt is not the authorization boundary.**
- **No authoritative current grants = no retrieval.**
- **The tier is not the authorization boundary.**

It is an educational implementation: synthetic data, one sandbox account, deployed and destroyed in one session. Read
[COST_AND_CLEANUP.md](COST_AND_CLEANUP.md) before deploying anything.

## 1. What is where

| Step of a request | Module | Control |
|---|---|---|
| 1 Identity and trusted request context | `app/query/trusted_context.py` | Uses only the verified `sub`; nothing else a client sends is an authorization input |
| 2 Authorization decision | `app/query/policy_decision.py`, `app/core/eligibility.py` | Fresh, consistent reads of employment status and grants for every request; any failure → no retrieval |
| 3 Tier selection | `app/core/tier_selection.py` | D3 layer 1 — blast-radius reduction. Restricted tier searched only for requesters with case assignments |
| 4 Constraint construction | `app/core/constraints.py` | D3 layer 2 — requester eligibility. Positive operators only, size budget, all or nothing |
| 5 Retrieval gateway | `app/query/retrieval_gateway.py` | The only code that calls the knowledge bases |
| 6 Before-generation verification | `app/core/verification.py` | Every chunk re-checked against the current classification record; any mismatch withholds everything |
| 7 Relevance | `app/core/relevance.py` | Answer quality only; it never sees the requester |
| 8 Generation | `app/query/generation.py` | In-Region model, no tools, no cache checkpoint |
| 9 Response handling | `app/query/response.py` | Citations only from verified chunks; one uniform non-answer |
| 10 Audit | `app/core/audit_record.py` | One content-free record per request |

**Ingestion** (`app/ingestion/`) reads labels only from the classification record, quarantines anything not exactly
valid (`app/core/classification.py`), drops special-category sections before anything is written
(`app/core/sections.py`), and writes one object per section to the tier its label belongs to.

**Infrastructure** is one CloudFormation template, `infrastructure/template.yaml`. Every role, bucket policy and table
permission is in that file: read it to answer "who can search the restricted tier?".

**Failure experiments** live outside this folder, in `../06-validation/sensitivity/`. Each replaces exactly one module
in its own throwaway deployment; the normal build refuses to package them.

## 2. The two layers of D3, in code

- `tier_selection.select_tiers()` decides **which knowledge bases** a request may touch. A requester with an SI-0417
  assignment is routed to the restricted tier — and that tier also holds HR-2031.
- `constraints.build_tier_queries()` builds the constraint that decides **which sections inside that tier** match:
  `andAll(label = RESTRICTED, scope in [SI-0417])`. Being in the right tier grants nothing; the constraint does.
- Test `TST-ELG-009` shows it on the deployed system, and experiment 1 shows what happens when the constraint is removed.

## 3. Run it

**Prerequisites:** Python 3.10+, `boto3` (and `pyyaml` for the template rules), a sandbox AWS account with Amazon
Bedrock model access to `amazon.titan-embed-text-v2:0` and `amazon.nova-micro-v1:0` in `us-east-1`, model invocation
logging disabled, and an AWS Budget with alerts.

```bash
# 0. local tests — no AWS, no credentials
python3 -m unittest discover -s tests                              # from 05-implementation/
(cd ../06-validation && python3 -m unittest discover -s tests)

# 1. configure (config/learner.env is git-ignored; it holds no secrets)
cp config/learner.env.example config/learner.env                   # set TLA_EXPECTED_ACCOUNT, profile, role path

# 2. preflight, build, deploy
python3 scripts/tla_ops.py preflight
python3 scripts/tla_ops.py build normal
python3 scripts/tla_ops.py deploy normal

# 3. load the synthetic corpus, personas and grants; run ingestion (from 06-validation/)
python3 -m harness fixtures load

# 4. ask as a persona, inspect the tiers, run the validation suite
python3 -m harness ask orion_pricing --as P-01
python3 -m harness inventory
python3 -m harness run --tests all

# 5. the three failure experiments (each deploys, breaks, destroys and restores)
python3 -m harness experiment 1
python3 -m harness experiment 2
python3 -m harness experiment 3

# 6. clean up — always
python3 ../05-implementation/scripts/tla_ops.py cleanup
python3 -m harness verify-cleanup
```

Or run everything unattended, the way the repeatability test does: `python3 -m harness full-run --label my-run`.

## 4. Teaching simplifications

The design lists them in `IMPLEMENTATION_DESIGN.md` §11. None removes a taught control. The most important one to
remember: the sandbox administrator who loads fixtures and runs the harness can read every tier — the harness says so
in its evidence instead of hiding it.

## 5. What this does not solve

Keeping the **index** current after a document is reclassified, deleted or re-versioned. This implementation keeps
**authorization** current: grants are read per request, and verification withholds anything whose classification has
changed. Re-indexing, downward reclassification propagation, deletions and stale embeddings are the next architecture
problem.
