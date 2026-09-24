# Episode 06 lab — what a citation does not tell you

**This lab reproduces the evidence that prevented an architecture decision. It does not implement one.**

Episode 06 asked how you decide whether changing the generation model still keeps the promise people
depend on. The engagement reached **no selected architecture** — and that outcome, with the evidence
behind it, is what you are about to run.

## What this lab teaches

By the end you will have established, from execution rather than assertion, that:

1. **Eligibility can pass, currency can pass, retrieval can succeed, the citation can resolve and every
   operational signal can be green — while the instruction in the answer is not carried by the section it
   cites.**
2. **A defensible change in where you draw the boundary of "one actionable claim" can change the
   serve / refuse decision** on the same answer, the same citation and the same procedure.

From which: **citation presence is not citation support**, and **a per-request control cannot reliably
discharge an obligation whose unit of enforcement has not been sufficiently defined.**

## The architectural problem

Episodes 01–03 moved two obligations *out* of the model: **eligibility** is a constraint inside retrieval,
**currency** is confirmed against the authority at request time. A model change cannot touch either.

One obligation was never moved out, because it lives in what the model says: **whether the answer is
actually carried by the authority it cites.** That is the one a model change can reach — and the one
nothing in the system checks.

## Prerequisites

Python 3.10+. **No AWS account. No API key. No model call. No cost. Nothing to clean up.**

## How to run it

```
cd 05-implementation
python3 lab_grounding.py                     # decide for yourself first
python3 lab_grounding.py --reveal            # then see what the procedure carries
python3 lab_grounding.py --reveal --extension  # optional: falsify a candidate architecture
```

## The sequence

| Step | What you do |
|---|---|
| 1 | Inspect the procedure — the authority everything is judged against |
| 2 | Inspect the controls Episodes 01–03 put in front of every answer |
| 3 | Run the normal case |
| 4 | Run the quiet case — **same citation, different instruction** |
| 5 | Two more of the same shape: a real value for the wrong component; an instruction that loses the condition limiting it |
| 6 | Run the segmentation case and watch the decision change |
| 7 | *(optional)* Falsify the quote-the-source candidate |
| 8 | Answer the architecture questions |

**The lab never tells you whether a claim is supported.** It shows you the controls' verdict and the
cited text, and you decide. That is not a shortcut — **whether support can be judged reliably is exactly
the question Episode 06 could not answer**, so the lab does not pretend to answer it either. `--reveal`
shows what the procedure carries, which is known only because the procedure was written for this lab.

## What this lab deliberately does NOT prove

- **It does not show how often this happens.** It shows the state is **reachable** and that the existing
  controls do not detect it. Frequency, probability and rate are **not** established.
- It says **nothing** about any real model, any provider, LLMs in general, or RAG systems in general.
- It does **not** show that AI verifiers cannot work, or that a second model would catch this. **Whether a
  verifier supplies independent evidence was not established** — that is one reason no architecture was
  selected.
- It does **not** show that human review is required for every AI system.
- It does **not** show that quoting the source solves or fails grounding in general. The optional
  extension falsifies three **specific** forms of one **candidate**.
- It is not a production safety or security certification.

## Synthetic data

The procedure, the entitlements and every answer are authored here. That is deliberate: it is the only
reason the lab can say what the procedure does and does not carry. It also bounds every claim the lab
makes to the cases in front of you.

## What it requires from you

Read D-204 before running anything, and read the cited section at each step before looking at `--reveal`.
The lab is a reading exercise wearing a program.

## How this relates to the episode

The episode reaches a non-selection. Five architecture options remained on the table — establish evidence
before promotion, verify each answer at serve time, do both, narrow what the system will answer, or stop
asserting instructions and quote the procedure. **The evidence did not justify choosing between them**,
and two of them could not be evaluated at all without a reference authority the engagement did not have.

**The absence of a selected architecture is part of the lesson, not a gap in it.**

## Questions to take away

- What did every control successfully establish, and what did none of them establish?
- What exactly is the unit of enforcement you would protect — and can you define it so that two competent
  engineers draw the same boundary?
- What would you need to see before calling a second verifier *independent*?
- **Which option can you defend from the evidence you have?** *"The evidence does not support selecting one
  yet"* is a complete and successful answer when you can defend it.

## What is in here

```
lab_grounding.py        the lab; run this
core/corpus.py          the procedure, its sections, and which sections limit which
core/controls.py        the Episodes 01-03 control chain, and the rung it cannot decide
core/cases.py           the answers you run the controls against
core/segmentation.py    two defensible claim boundaries
core/extraction.py      optional: falsifying the quote-the-source candidate
```
