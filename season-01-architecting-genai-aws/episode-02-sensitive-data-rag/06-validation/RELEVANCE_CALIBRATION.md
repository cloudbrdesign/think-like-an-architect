# Relevance Calibration — Kestrelmoor Knowledge Assistant

**Date:** 2026-09-15 · **Region:** us-east-1 · **Deployment:** normal educational deployment, synthetic corpus

> **Relevance is not authorization.** The threshold decides whether an *eligible, verified* chunk is useful enough to
> answer with. It never decides whether the requester may see a chunk: authorization is decided before retrieval by
> the mandatory constraint, and re-checked by verification before relevance runs. `core/relevance.py` receives only
> verified chunks and nothing about the requester.

## 1. Method

1. For 8 personas that can be answered at all (P-01…P-07, P-10) and 20 non-attack questions, each tier the persona's
   decision selects was searched **with that persona's mandatory constraint**, built by `core/constraints.py` — the same
   builder the query function uses. Operator credentials (a privileged harness path), no generation.
2. Every (persona, question) pair was classified:
   - **answerable** — the question's target section is indexed and eligible for the persona; its score must clear the
     threshold;
   - **no-target** — the topic exists nowhere the persona may see; its best score should not;
   - **not-answerable** — the target is not eligible, but related eligible content exists (informational only).
3. Every threshold from 0.20 to 0.90 was scored for false negatives (answerable targets below it) and kept no-target
   pairs.
4. **Selection rule** (coarse on purpose, so no single query can tune it): on a 0.05 grid, the highest threshold at
   least 0.05 below the weakest answerable target score. Recall of eligible answers comes first; a kept but unhelpful
   chunk is handled by the model's fixed instruction to reply with the uniform no-answer sentence, which the response
   handler turns into the uniform response.

## 2. Observations

| Measure | Value |
|---|---|
| Answerable pairs | 64 — lowest target score **0.6696** (P-05, a witness named only inside D-04 §2); every topical question's target scored **0.8385–0.9279** |
| No-target pairs | 15 — highest best score **0.6217** (P-05, an invented witness name close to the SI-0417 witness statements); all other no-target pairs **0.5488–0.5589** |
| Not-answerable pairs | 81 — best scores 0.6155–0.8148 (related eligible content, for example Orion lessons for an Orion pricing question) |
| Retrieval misses (answerable target not returned at all) | none |

| Threshold | False negatives | No-target pairs kept | Not-answerable pairs kept |
|---|---|---|---|
| 0.55 | 0 | 8 | 81 |
| **0.60 (selected)** | **0** | **1** | **81** |
| 0.65 | 0 | 0 | 67 |
| 0.70 | 1 | 0 | 29 |
| 0.75 | 1 | 0 | 15 |

## 3. Selected threshold and reason

**0.60.** It is the highest 0.05-grid value at least 0.05 below the weakest answerable target score (0.6696):
- **Eligible answers:** no answerable pair is lost.
- **No-target pairs:** one keeps a chunk; the model then gives the uniform no-answer sentence.
- **Why not 0.65:** it would also exclude that pair, but it sits 0.02 below the weakest answerable score — a tuning
  to two queries, not a margin.

**False-negative implication:** a real question whose best eligible section scores below 0.60 gets the uniform
"cannot answer" response even though an eligible answer exists. Short name-only questions scored lowest in this corpus.

**Limitation:** these scores come from one embedding model, one corpus of 22 short synthetic sections, and this
service's scoring under the tested conditions. They are not portable. A real corpus needs its own calibration, and an
evaluated answer-quality policy (teaching simplification TS-E02-07).

## 4. Authorization independence — observed

| Observation | Result |
|---|---|
| A highly relevant **ineligible** section stays ineligible | For P-01's Orion pricing question, an unconstrained operator search ranks D-03 §4 **first**; the constrained search for P-01 does not return it at all, so relevance never sees it |
| An eligible **low-relevance** section can be omitted without changing its authorization | In TST-ELG-004 (P-01, Orion lessons) two eligible, verified sections scored about 0.55 and were omitted from generation (`relevance.omitted` in the audit record) while verification recorded PASS; they remain eligible for any request where they are relevant |

## 5. Evidence

- `07-evidence/implementation-validation-2026-09-15/relevance-calibration/relevance-calibration.json` — every
  observation, the full threshold table and the independence searches.
- Audit records of the validation run — `relevance.min_score`, `relevance.kept`, `relevance.omitted` per request.
