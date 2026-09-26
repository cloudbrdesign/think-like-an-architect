#!/usr/bin/env python3
"""Episode 07 lab -- failing over without silently changing the promise.

    python3 lab_failover.py --step 1 .. 6
    python3 lab_failover.py --attack 1 .. 4
    python3 lab_failover.py --all

No AWS account. No API key. No model call. No network. No cost. Nothing to clean up.
"""
import argparse
import sys

from core import mapping as mapping_mod
from core import paths as paths_mod
from core.decide import (CANNOT_DETERMINE_OBLIGATIONS, CANNOT_ESTABLISH_PERMISSION_TO_ANSWER, ESTABLISH,
                         INHERIT, MUST_NOT_ANSWER, decide)
from core.procedures import PROCEDURE, RecordsSystem

RULE = "-" * 96


def scenario(asserted_at=0, withdraw_at=1, now=2, issuer_anchored=False):
    """One incident, held fixed for every step: the instruction is withdrawn DURING the partition."""
    records = RecordsSystem()
    records.withdraw("D-204-S1", withdraw_at)
    records.tick = now
    path = (paths_mod.failover_with_issuer_window(asserted_at) if issuer_anchored
            else paths_mod.failover_with_replica(asserted_at))
    return records, path


def show(label, rec, fields=("outcome", "reason", "cause", "currency_basis", "o6_grounding")):
    print(f"  {label:<34}" + "  ".join(f"{f}={rec[f]}" for f in fields if rec[f] is not None))


def step1():
    print(RULE); print("STEP 1 -- the authority, and what 'in force' means")
    print("\n  A technician acts on an answer without opening the procedure. That promise rests on the")
    print("  answer being carried by authority that is IN FORCE. Only the records system can say so.\n")
    for s in PROCEDURE.values():
        print(f"  {s.section_id}  actionable={str(s.actionable):<5} {s.text}")
    print("\n  THE NORMAL CONDITION. Nothing has failed. The primary path serves, and it serves because it")
    print("  established the obligation on this request -- it reached the authority and got an answer:\n")
    quiet = RecordsSystem(); quiet.tick = 0
    show("primary path, normal:", decide(paths_mod.primary(), quiet, True, "D-204-S1"))
    print("\n  Hold on to that `currency_basis=CONFIRMED`. It is the only basis in this lab that means the")
    print("  system asked the authority and the authority answered. Everything after this is a copy.")
    records, _ = scenario()
    print(f"\n  During the incident the records owner withdraws D-204-S1 at logical tick 1.")
    print(f"  Authoritative state at tick {records.tick}: "
          + ", ".join(f"{k}={'in force' if v else 'WITHDRAWN'}" for k, v in records.snapshot(records.tick).items()))
    print("\n  'Logical tick' is an ordering, not a duration. This lab contains no seconds, and no budget.")


def step2():
    print(RULE); print("STEP 2 -- the failover path that INHERITS permission")
    records, path = scenario()
    print("\n  The primary inference path degrades. The second region takes over. Its dashboard:")
    print(f"    {path.health()}   authority_reachable={path.authority_reachable}")
    print("\n  It was certified before the incident, so it answers. Ask it for the withdrawn instruction:\n")
    rec = decide(path, records, True, "D-204-S1", behaviour=INHERIT)
    show("inheriting path:", rec)
    print(f"\n  It served '{PROCEDURE['D-204-S1'].text}'")
    print("  That instruction was withdrawn one tick before the request. Nothing failed. No alarm fired.")
    print("  Every signal a normal dashboard carries is green -- and none of them is about authority.")
    print("\n  This is the episode's subject: a failover event INHERITED permission to answer.")
    print("\n  FAILOVER CAN RESTORE AVAILABILITY WITHOUT RESTORING AUTHORITY. A healthy serving path is not")
    print("  by itself evidence that the path is entitled to answer.")


def step3():
    print(RULE); print("STEP 3 -- the decision: establish, or do not serve as though you had")
    records, path = scenario()
    print("\n  Same incident, same request, same path. The only change is that the path must ESTABLISH")
    print("  the obligation on this request instead of inheriting it:\n")
    show("establishing path:", decide(path, records, True, "D-204-S1", behaviour=ESTABLISH))
    print("\n  Now the four conditions that must never collapse into one another:\n")
    show("caller prohibited:", decide(path, records, False, "D-204-S1"))
    show("permission unknowable:", decide(path, records, None, "D-204-S1"))
    show("authority unreachable:", decide(path, records, True, "D-204-S1"))
    unreachable = paths_mod.Path("failover", path_reachable=False)
    show("infrastructure down:", decide(unreachable, records, True, "D-204-S1"))
    print("\n  Four callers see two of Episode 04's four outcomes -- the contract is unchanged, and there")
    print("  is no fifth outcome here. Underneath, MUST_NOT_ANSWER and CANNOT_ESTABLISH_PERMISSION_TO_ANSWER")
    print("  stay distinct in the record, which is what an incident review and a regulator need.")


def step4():
    print(RULE); print("STEP 4 -- reduce capability, not trust")
    records, path = scenario()
    print("\n  Not every answer needs current authority. A governed mapping says which do:\n")
    for section_id in PROCEDURE:
        required, basis = mapping_mod.Mapping().lookup(section_id)
        print(f"  {section_id}  requires_current_confirmation={str(required):<5} {basis}")
    print("\n  So during the partition the assistant keeps the classes it can still establish:\n")
    for section_id in ("D-900-S1", "D-204-S1"):
        show(f"{section_id}:", decide(path, records, True, section_id))
    print("\n  Capability is reduced. Trust is not. The technician gets less, never something weaker.")
    print("  The mapping is governed state, and step 4's attacks (--attack 1, 2, 3) are about who owns it.")


def step5():
    print(RULE); print("STEP 5 -- relocating the dependency is not the same as being current")
    records, dependent = scenario()
    _, independent = scenario(issuer_anchored=True)
    print("\n  Option E's idea: carry the authority's decision with the content, so no call is needed.")
    print("  Compare two carried assertions under the same partition:\n")
    for label, path in (("dependent copy:", dependent), ("independent issuer:", independent)):
        rec = decide(path, records, True, "D-204-S1")
        prov = ", ".join(rec["assertion_provenance"])
        print(f"  {label:<22} outcome={rec['outcome']}  basis={rec['currency_basis']}")
        print(f"  {'':<22} provenance=[{prov}]")
    print("\n  The issuer-anchored assertion IS independent of the failed route -- and it is still only as")
    print("  current as the tick it was issued at, which precedes the withdrawal. Independence and")
    print("  currency are different properties. Relocation moved the dependency; it did not remove it.")
    print("\n  Where the governing contract permits it, the same state can be served as declared degraded:")
    show("declared degraded:", decide(independent, records, True, "D-204-S1", contract_permits_degraded=True))
    print("\n  Note what that requires: the contract must PERMIT it. The default here is refusal, because")
    print("  permission to answer-with-disclosure is a ruling someone has to make, not a default.")
    print("  Whether a technician told 'this may have changed' behaves any differently is NOT tested by")
    print("  this lab, and no result here claims it.")


def step6():
    print(RULE); print("STEP 6 -- the number this lab refuses to invent")
    records, path = scenario()
    rec = decide(path, records, True, "D-204-S1")
    print(f"\n  The carried assertion is one logical tick older than the withdrawal.")
    print(f"  currency_detail: {rec['currency_detail']}")
    print("\n  A bounded-staleness architecture would say: 'below age X, treat the assertion as")
    print("  confirmation.' That is a policy decision about what risk is tolerable for an actionable")
    print("  instruction, and it belongs to Safety & Compliance. It is not a measurement, and this lab")
    print("  will not supply it.\n")
    print("    THRESHOLD / POLICY AUTHORITY REQUIRED")
    print("\n  Until someone with that authority states a window -- or states that none is tolerable --")
    print("  the architecture stops at: establish it, or do not serve as though you had.")
    print(f"\n  And one obligation is not in the invariant at all. o6_grounding={rec['o6_grounding']}:")
    print("  whether the answer is CARRIED BY the section it cites is not computed anywhere in this lab.")
    print("  You adjudicate it. That is honest about what the engagement established, and what it did not.")


def attack(n):
    records, path = scenario()
    print(RULE)
    if n == 1:
        print("ATTACK 1 -- delete the mapping. Does anything default to serving?\n")
        m = mapping_mod.Mapping(entries={})
        outcomes = {s: decide(path, records, True, s, mapping=m) for s in PROCEDURE}
        for s, rec in outcomes.items():
            show(f"{s}:", rec, ("outcome", "cause", "reason"))
        held = all(r["cause"] == CANNOT_DETERMINE_OBLIGATIONS for r in outcomes.values())
        print(f"\n  FAIL-CLOSED HELD: {held}. With no mapping, nothing is served and the record says why.")
        return held
    if n == 2:
        print("ATTACK 2 -- the records owner waives an obligation by editing the mapping.\n")
        entries = dict(mapping_mod.AUTHORED)
        entries["D-204-S1"] = mapping_mod.Entry(
            "D-204-S1", False, "edited: no longer requires confirmation",
            mapping_mod.RECORDS_OWNER, None, "mapping-2026-09-26.2-unauthorised")
        rec = decide(path, records, True, "D-204-S1", mapping=mapping_mod.Mapping(entries=entries))
        show("edited entry:", rec, ("outcome", "cause", "reason"))
        held = rec["cause"] == CANNOT_DETERMINE_OBLIGATIONS
        print(f"\n  FAIL-CLOSED HELD: {held}. Content ownership is not exemption authority. Waiving a safety")
        print("  obligation needs Safety & Compliance to declare it, and an entry without that declaration")
        print("  is not an entry. The edit cannot buy permission.")
        return held
    if n == 3:
        print("ATTACK 3 -- fetch the mapping across the route that failed.\n")
        m = mapping_mod.Mapping(fetch_route=path.broken_route)
        rec = decide(path, records, True, "D-204-S1", mapping=m)
        show("mapping across route:", rec, ("outcome", "cause", "reason"))
        held = rec["cause"] == CANNOT_DETERMINE_OBLIGATIONS
        print(f"\n  FAIL-CLOSED HELD: {held}. Put the mapping behind the failed boundary and capability")
        print("  reduction stops working -- it collapses into the per-request rule with extra parts.")
        return held
    if n == 4:
        print("ATTACK 4 -- sign and cache the dependent copy. Does a local signature make it current?\n")
        a = path.carried["D-204-S1"]
        a.provenance = ["local-cache", "signature-verified-locally"] + a.provenance
        rec = decide(path, records, True, "D-204-S1")
        show("signed and cached:", rec, ("outcome", "cause", "currency_basis"))
        print(f"  {'':<34}provenance={rec['assertion_provenance']}")
        held = rec["cause"] == CANNOT_ESTABLISH_PERMISSION_TO_ANSWER
        print(f"\n  FAIL-CLOSED HELD: {held}. The signature verifies locally and attests something that came")
        print("  across the failed route. Verifying a copy is not reaching the authority.")
        return held
    raise ValueError(f"no such attack: {n}")


STEPS = {1: step1, 2: step2, 3: step3, 4: step4, 5: step5, 6: step6}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", type=int, choices=sorted(STEPS))
    ap.add_argument("--attack", type=int, choices=(1, 2, 3, 4))
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)
    if args.all:
        for fn in STEPS.values():
            fn(); print()
        held = [attack(n) for n in (1, 2, 3, 4)]
        print(RULE)
        print(f"every attack failed closed: {all(held)}")
        return 0 if all(held) else 1
    if args.step:
        STEPS[args.step]()
        return 0
    if args.attack:
        return 0 if attack(args.attack) else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
