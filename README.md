# Think Like an Architect

> **Free architecture education.** Every engagement here is free to read, work through and build in your own cloud
> account. No purchase is needed to complete an engagement.

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
LICENSING.md                           which licence applies where
LICENSES/                              licence texts (Apache-2.0, CC-BY-4.0)
CONTRIBUTING.md                        how changes are made and reviewed
templates/                             reusable engagement templates
tools/                                 boundary and traceability checks
season-01-architecting-genai-aws/      Season 1 episodes
```

## Before you run anything

Episodes deploy real resources into **your own** cloud account. Every episode states its billable resources, cost
drivers and cleanup steps **before** the first deployment step. Always run the cleanup.

## Status

The engagement templates are available in [templates/](templates/README.md). Episode 01 is available: the complete
engagement, the educational implementation, its validation suite and an example evidence set. Start at
[the Episode 01 README](season-01-architecting-genai-aws/episode-01-multi-tenant-rag/README.md). Episode 02 is available too:
the engagement, implementation, validation suite, three failure experiments and an example evidence set — start at
[the Episode 02 README](season-01-architecting-genai-aws/episode-02-sensitive-data-rag/README.md). Episode 03 is available:
a two-part learner lab — a stale copy that is retrieved and refused, then a failed change that is retried, escalated
and recovered — with the engagement, implementation and an evidence summary; start at
[the Episode 03 README](season-01-architecting-genai-aws/episode-03-keeping-knowledge-current/README.md). The season overview is
[season-01-architecting-genai-aws/README.md](season-01-architecting-genai-aws/README.md).

## Licence

Code is licensed under Apache-2.0; educational content and documentation under CC BY 4.0. See
[LICENSING.md](LICENSING.md).
