# Episode 05 lab — cost without breaking answers

**Think Like an Architect — Season 1, Episode 05.**

Three engagements made this assistant trustworthy, and each did it by doing work on every request: deciding
who may see a section, confirming the source is still in force, and keeping both promises under load. Then
the bill arrived.

The cost is not waste. It is the price of that correctness. So every credible saving is a proposal to do
less of exactly the work that makes an answer trustworthy — and the hard question is which of that
expensive work is **load-bearing**, and which is **merely expensive**. On an invoice they look identical.

---

## Start here

**[`05-implementation/README.md`](05-implementation/README.md)** — what the lab teaches, how to run it,
and what each line of its output means.

```bash
cd 05-implementation
python3 lab_reuse.py
```

**Python 3.10 or newer. Nothing else.** No AWS account, no credentials, no network, no billable resources,
and nothing to clean up.

## What the lab shows

It turns on one safe reuse mode and then takes away the things that made reuse valid:

1. the reference path — the authorised, current computation;
2. a legitimate reuse hit, and the preservation work that hit costs;
3. an entitlement revoked — reuse **refuses**;
4. the source procedure withdrawn — reuse **refuses**;
5. **one of three** carried sections withdrawn — reuse still **refuses**;
6. what was removed, and what had to be kept.

The number worth staring at is in step 6: the authority confirmations are the **same** in both rows. Reuse
removed the generation and the retrieval. It did not remove the obligation to confirm, on every serve, that
every carried section is still authorised and still in force.

## What it deliberately does not prove

It counts operations. **It does not price them.** The repetition in it is synthetic — written to create a
reuse opportunity, not observed in any production system. Fewer calls is an accounting result, not a proven
monetary saving.

## Fiction and safety

Kestrelmoor Rail Systems is fictional and every document, procedure and person in the lab is synthetic,
written for teaching. **Do not use any procedure text in this lab as real safety instruction.**

## Licence

Code under Apache-2.0; educational content and documentation under CC BY 4.0. See
[`../../LICENSING.md`](../../LICENSING.md).
