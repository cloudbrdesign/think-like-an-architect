# 06-validation — learner lab tooling

This folder holds what the Episode 03 lab needs to run:

| Path | What it is |
|---|---|
| `harness/lab.py` | The `lab-*` commands: ask, inspect, withdraw, reconcile, obstruct, reclassify-up, incident, unobstruct |
| `harness/` (other modules) | What those commands use: the deployment's outputs, the synthetic identities, the records system, the convergence store, and the fixture loader that `lab-up` runs |
| `fixtures/` | The synthetic corpus: 15 documents, 11 employees, questions and change scenarios |
| `tests/test_learner_lab.py` | Component tests for the lab commands. Standard library only, no AWS: `python3 -B -m unittest discover -s tests` |

Run the lab from the [episode README](../README.md). Every `python3 -m harness …` command runs from this folder.

The implementation was also validated with a larger test suite and a set of failure experiments. That suite is not
part of this package; what it observed is summarised in [EVIDENCE_SUMMARY.md](../EVIDENCE_SUMMARY.md).
