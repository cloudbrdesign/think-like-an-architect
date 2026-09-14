# Think Like an Architect

> **Repository status: PRIVATE STAGING.** This repository will hold free, public architecture education. It is private
> only while its structure and first engagement are being established. Nothing has been published yet.

**Think Like an Architect** teaches architectural thinking. Every episode is a simulated professional architecture
engagement, run end to end:

**business problem → requirements → constraints → options → decisions → architecture → implementation → validation →
evidence**

The video teaches the thinking. This repository teaches the doing.

## What this is — and is not

| This is | This is not |
|---|---|
| A complete, free architecture engagement per episode | A service tutorial or a copy/paste lab |
| A working learner implementation you build yourself | A certification or certification-preparation course |
| Validation that proves requirements — including tests that must be **refused** | "It deployed, so it works" |
| Guidance for assembling portfolio evidence of the work you performed | An independent assessment of competence |

## Repository layout

```
README.md                              this file
LICENSING.md                           licensing status
CONTRIBUTING.md                        how changes are made and reviewed
templates/                             reusable engagement templates
tools/                                 boundary and traceability checks
season-01-architecting-genai-aws/      Season 1 episodes
```

## Before you run anything

Episodes deploy real resources into **your own** cloud account. Every episode states its billable resources, cost
drivers and cleanup steps **before** the first deployment step. Always run the cleanup.

## Status

The engagement templates are available in [templates/](templates/README.md). Episode 01 is in implementation design; see
[season-01-architecting-genai-aws/README.md](season-01-architecting-genai-aws/README.md).
