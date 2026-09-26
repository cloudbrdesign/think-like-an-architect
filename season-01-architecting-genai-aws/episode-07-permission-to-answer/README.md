# Episode 07 lab — how to fail over without silently changing the promise

**Think Like an Architect — Season 1, Episode 07.**

**This lab teaches the architecture decision the engagement reached. It is not the engagement's
validation harness, and it shares no code with it.**

Kestrelmoor's depot assistant answers procedural questions that technicians act on at the equipment.
The promise is small and load-bearing: **a technician can act on an answer without opening the
procedure.** Episode 07 asks what happens to that promise when the primary inference path degrades and
a second region takes over — a second region whose index is a replica and whose route to the records
system crosses the boundary that is currently unreliable.

---

## Start here

**[`05-implementation/README.md`](05-implementation/README.md)** — what the lab teaches, how to run it,
and what each step means.

```bash
cd 05-implementation
python3 lab_failover.py --step 1
```

**Python 3.10 or newer. Nothing else.** No AWS account, no credentials, no API key, no network, no model
call, no billable resources, and nothing to clean up.

## What you will establish, by running it

1. **A failover path can be completely healthy and still answer without permission.** Every ordinary
   signal is green, the citation resolves, the requester is entitled — and the instruction it serves was
   withdrawn a moment earlier.
2. **Availability signals cannot see it.** They recover on failover by construction. That is what
   failover is for, and it is why none of them carries this distinction.
3. **The decision that fixes it is an invariant, not a topology:** *establish the obligation on this
   request, or do not serve as though you had.*
4. **Reducing capability is not reducing trust** — and the mapping that decides which requests can still
   be served is **governed state** with two separate owners.
5. **Relocating a dependency is not the same as being current.** An independently-anchored assertion is
   genuinely independent of the failed route, and still only as current as the moment it was issued.
6. **Where the number would go, and why this lab refuses to put one there.**

## The architectural problem

Episodes 01–05 deliberately moved obligations *out* of the model and into components Kestrelmoor
controls: entitlement became a constraint inside retrieval, currency became a confirmation against the
records system at request time. That is what made them safe against a model change.

**A failover replaces exactly those components.** The retrieval is now a replica. The route to the
records system is across the boundary that is failing. So the question is not *can we keep producing
text* — the second region does that fine. It is **whether this path is entitled to answer at all**.

## Fiction and safety

Kestrelmoor Rail Systems is fictional and every procedure, section and person in this lab is synthetic,
written for teaching. **Do not use any procedure text in this lab as real safety instruction.**

## Licence

Code under Apache-2.0; educational content and documentation under CC BY 4.0. See
[`../../LICENSING.md`](../../LICENSING.md).
