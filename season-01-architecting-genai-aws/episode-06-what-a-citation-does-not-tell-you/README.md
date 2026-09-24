# Episode 06 lab — what a citation does not tell you

**Think Like an Architect — Season 1, Episode 06.**

The assistant has been trustworthy for three episodes because two obligations were moved *out* of the
model: who may see a section is decided inside retrieval, and whether it is still in force is confirmed
against the records system on every request. A change of model cannot touch either.

One obligation was never moved out, because it lives in what the model says — **whether the answer is
actually carried by the authority it cites.** When the model version has to change, that is the one thing
at risk, and nothing in the system checks it.

---

## Start here

**[`05-implementation/README.md`](05-implementation/README.md)** — what the lab teaches, how to run it,
and what each step means.

```bash
cd 05-implementation
python3 lab_grounding.py
```

**Python 3.10 or newer. Nothing else.** No AWS account, no credentials, no API key, no network, no model
call, no billable resources, and nothing to clean up.

## What the lab shows

1. the procedure everything is judged against;
2. the controls Episodes 01–03 put in front of every answer;
3. a normal answer — every control green;
4. **the same citation, a different instruction** — every control still green;
5. a real value quoted for the wrong component, and an instruction that loses the condition limiting it;
6. one answer, two defensible ideas of what "one claim" is — **and the serve decision changes**;
7. *(optional)* three ways that quoting the procedure instead still fails to keep the promise;
8. the architecture questions.

The moment worth stopping on is step 4. Nothing in the control chain distinguishes **40 Nm** from **60 Nm**
when both cite the same section. Every control reads the *inputs* to the answer. None reads the answer.

## This lab does not contain an architecture

**Episode 06 selected none.** Five options stayed on the table — establish evidence before promotion,
verify each answer as it is served, do both, narrow what the system will answer, or stop asserting
instructions and quote the procedure. The evidence did not justify choosing between them, and two could
not be evaluated at all without a reference authority the engagement did not have.

**That is the lesson, not a gap in it.** This lab reproduces the evidence that prevented the decision.

## What it deliberately does not prove

It shows the failure state is **reachable** and that the existing controls do not detect it. It does
**not** show how often it happens, says **nothing** about any real model or about LLMs or RAG systems in
general, does **not** show that a verifier would or would not catch it, and does **not** show that quoting
the source solves or fails grounding generally. It is not a production safety or security certification.

## Fiction and safety

Kestrelmoor Rail Systems is fictional and every document, procedure and person in the lab is synthetic,
written for teaching. **Do not use any procedure text in this lab as real safety instruction.**

## Licence

Code under Apache-2.0; educational content and documentation under CC BY 4.0. See
[`../../LICENSING.md`](../../LICENSING.md).
