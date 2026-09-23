# Episode 05 lab — what reuse costs you to keep correct

A completely local, 60-second lab. **No AWS account. No credentials. No network. No spend. Nothing to
clean up.**

---

## What this lab teaches

When a system answers the same question twice, the obvious optimisation is to keep the first answer and
serve it again. The saving is easy to see: a retrieval and a generation disappear.

What is much harder to see is the work you have to **add** to be allowed to do that — and that work does
not show up on the dashboard that made the optimisation look good.

This lab makes both halves visible at once:

```
        WORK REMOVED                    PRESERVATION WORK RETAINED / ADDED
        generation calls                authority confirmations
        retrieval calls                 metadata carriage
                                        equivalence checks
                                        invalidation / currency work
```

## The architectural problem

A reused answer is a **derived copy**. It was correct for one requester, at one moment, from a particular
set of source sections. Any of those three can change afterwards:

- the requester's entitlement can be **revoked**;
- a source procedure can be **withdrawn**;
- **one of several** carried sections can be withdrawn while the others stay valid.

If reuse does not re-check all three on **every** serve, it will keep serving confidently and the failure
will be silent. That is what you are here to see.

## Prerequisites

- **Python 3.10 or newer** (`python3 --version`). The dataclass syntax used needs 3.10+.
- Nothing else. No packages to install, no `requirements.txt`, no virtual environment needed.

## How to run it

```bash
cd season-01-architecting-genai-aws/episode-05-cost-without-breaking-answers/05-implementation
python3 lab_reuse.py
```

Exit code `0` and about 60 lines of output.

## Expected learner-visible output, and what each part means

| Step | What you see | What it means |
|---|---|---|
| **1** | `served: True`, sections `['D-100#1', 'D-100#2', 'D-100#3']`, then `ORIGINAL retrieval_calls=1 context_sections=3 authority_confirmations=3 generation_calls=1` | The **reference path** — the authorised, current computation. Every later measurement is taken against this, so the optimisation never gets to define its own baseline. |
| **2** | `second identical request served from reuse: True` and `the answer is the SAME text, not a new one: True` | A legitimate hit. The second request cost no retrieval and no generation — but note `metadata_writes` and `equivalence_checks` appearing under **PRESERVATION**. |
| **3** | `served: False` · `refused because: entitlement no longer permits a carried section` | The stored answer was still there. Entitlement is re-checked at **serve** time, not at store time, because a grant can be revoked after the answer was made. |
| **4** | `served: False` · `a carried section is no longer in force (D-100#1)` | The source procedure was withdrawn. A derived copy of withdrawn guidance is still withdrawn guidance. |
| **5** | carries 3 sections, `withdrawing only D-102 → served=False`, `refused because of: D-102#1` | **The one that matters.** Only the *third* carried section was withdrawn. A design that re-checked only the first would have served a withdrawn step here. |
| **6** | `reference: generation_calls=2 retrieval_calls=2 authority_confirmations=6` vs `reuse: generation_calls=1 retrieval_calls=1 authority_confirmations=6` plus `metadata_writes=1 equivalence_checks=1` | The whole lesson in three lines. Generation and retrieval halved. **`authority_confirmations` did not move** — and two new preservation counters appeared. |

**The number to stare at is `authority_confirmations`.** It is identical in both rows. Reuse removed the
generation and the retrieval; it did not remove the obligation to confirm, on every serve, that every
carried section is still authorised and still in force. That obligation is the price of being allowed to
reuse anything at all.

## What this lab deliberately does NOT prove

- **It does not prove that reuse pays.** It counts operations. It does not price them.
- **The repetition is synthetic.** It was written to create a reuse opportunity. It is not observed
  production traffic, and no rate in this lab represents any real system's traffic.
- **It is not a benchmark, and there is no winner.** Episode 05's own economic finding was:

  ```
  COST-004 = NOT EMPIRICALLY RESOLVED IN THIS EPISODE
  ```

  Fewer calls is an **accounting** result. A proven monetary saving is a different and much more
  expensive claim, and Episode 05 does not make it for any candidate.

- It shows **one** safe reuse mode. It is not a survey of caching strategies.

## Synthetic data

**Kestrelmoor Rail Systems is fictional.** Every document, section, procedure and person in `core/corpus.py`
was written for teaching. Nothing here is real operational content, real safety guidance, or observed
production data. **Do not use any procedure text in this lab as actual safety instruction.**

## What it requires from you

| | |
|---|---|
| AWS account | **NONE** |
| AWS credentials | **NONE** |
| Any credentials at all | **NONE** |
| Network access | **NONE** |
| Billable resources created | **NONE** |
| Cleanup required | **NONE** — nothing is created, so there is nothing to remove |

The answer generator is local and deterministic *by design*. Episode 05 measured real model output at
`temperature = 0` and found it **was not deterministic** — so a lab built on live inference would hand
every learner different numbers for reasons that have nothing to do with the architecture being taught.

## Safety boundary

This lab only ever shows the equivalence control **working**. There is deliberately no way to switch the
serve-time checks off here, and no unsafe implementation ships in this repository.

Episode 05 did run a version with those checks removed, and the result is part of the episode's argument:
the optimisation kept serving, the hit rate stayed healthy, the cost-facing metrics stayed healthy — and
withdrawn and revoked content was served anyway. **The failure was quiet.** That demonstration is
instructor-run evidence shown in the episode. It is not learner-deployable code, and it is not here.

The lesson is **not** "caching is unsafe." It is: **reuse is only valid while the equivalence assumptions
that justified it still hold.**

## How this relates to the episode

The episode asks whether a set of plausible optimisations actually pay once you count the work that keeps
them correct. This lab is the part you can run yourself: it shows what disappears, and what does not.

## Two questions to take away

1. **In your own system, what would the equivalence check have to re-verify on every serve** — and would
   you notice if it silently stopped running?
2. **If you removed the generation call but kept every authority confirmation, what did you actually
   save** — and how would you prove it, given that the cost you removed and the cost you kept are counted
   in different units?

## What is in here

```
05-implementation/
├── README.md          this file
├── lab_reuse.py       the lab — run this
└── core/              the publishable learner-safe core
    ├── corpus.py      synthetic documents, sections, entitlements, document states
    ├── reference.py   the reference path: eligibility → currency → retrieval → generation
    ├── reuse.py       one safe reuse mode, with serve-time re-checking
    ├── instrument.py  the consumption meter: ORIGINAL vs PRESERVATION
    └── provider.py    local deterministic answer generator
```

`core/` depends on nothing outside itself.
