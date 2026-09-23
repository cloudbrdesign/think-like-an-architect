#!/usr/bin/env python3
"""Episode 05 — PUBLIC LEARNER LAB · what reuse costs you to keep correct.

Kestrelmoor Rail Systems is fictional and all data is synthetic. Runs entirely locally: no cloud
account, no credentials, no network, no billable resource, nothing to clean up.

You will:
  1. run the REFERENCE path — the authorised, current computation
  2. turn on ONE safe INTERNAL reuse mode and see a legitimate hit
  3. revoke an entitlement and watch the reuse path REFUSE
  4. withdraw the source procedure and watch it REFUSE again
  5. withdraw only ONE of several carried sections — and watch it still refuse
  6. compare consumption before and after, INCLUDING the work you had to keep

Two questions to answer by the end:
    What did we save?
    What work did we have to retain to make that saving safe?

Usage:  python3 lab_reuse.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from core import corpus, instrument, reference, reuse            # noqa: E402
from core.provider import LocalProvider                          # noqa: E402

Q = "how do I isolate a points machine"
Q_MULTI = "shift handover and isolation"


def banner(n, t):
    print(f"\n{'─' * 74}\n  STEP {n} — {t}\n{'─' * 74}")


def show(meter, label):
    c = meter.by_category()
    print(f"    {label}")
    for cat in ("ORIGINAL", "PRESERVATION"):
        if c[cat]:
            print(f"      {cat:13s} " + " · ".join(f"{k}={v}" for k, v in sorted(c[cat].items())))


def fresh():
    for d in corpus.DOCUMENTS.values():
        d.state = "IN_FORCE"
    for p in corpus.PRINCIPALS.values():
        p.active = True


def main():
    reference.register(Q, ["D-100#1", "D-100#2", "D-100#3"])
    reference.register(Q_MULTI, ["D-100#1", "D-101#1", "D-102#1"])
    p = LocalProvider()
    tech = corpus.PRINCIPALS["P-01"]
    fresh()

    banner(1, "the reference path: eligibility → currency → retrieval → generation")
    m_ref = instrument.Meter()
    r = reference.answer(Q, tech, p, m_ref)
    print(f"    served: {r['served']}   sections: {r['sections']}")
    show(m_ref, "one answer, computed from scratch:")

    banner(2, "turn on INTERNAL answer reuse — and get a legitimate hit")
    m = instrument.Meter()
    store = reuse.ReuseStore()
    first = reference.answer(Q, tech, p, m)
    store.retain(Q, [corpus.SECTIONS[i] for i in first["sections"]], first["text"], m)
    hit = store.serve(Q, tech, m)
    print(f"    second identical request served from reuse: {hit['served']}")
    print(f"    the answer is the SAME text, not a new one: {hit['text'] == first['text']}")
    show(m, "two requests, one of them reused:")

    banner(3, "revoke the requester's access — the reuse path must REFUSE")
    fresh()
    m3 = instrument.Meter()
    s3 = reuse.ReuseStore()
    a = reference.answer(Q, tech, p, m3)
    s3.retain(Q, [corpus.SECTIONS[i] for i in a["sections"]], a["text"], m3)
    tech.active = False
    out = s3.serve(Q, tech, m3)
    print(f"    served: {out['served']}")
    print(f"    refused because: {out['reason']}")
    print("    NOTE: the stored answer was still there. Entitlement is re-checked at SERVE time,")
    print("          not at store time — because a grant can be revoked after the answer was made.")

    banner(4, "withdraw the source procedure — the reuse path must REFUSE")
    fresh()
    m4 = instrument.Meter()
    s4 = reuse.ReuseStore()
    a4 = reference.answer(Q, tech, p, m4)
    s4.retain(Q, [corpus.SECTIONS[i] for i in a4["sections"]], a4["text"], m4)
    corpus.DOCUMENTS["D-100"].state = "WITHDRAWN"
    out4 = s4.serve(Q, tech, m4)
    print(f"    served: {out4['served']}")
    print(f"    refused because: {out4['reason']}  (section {out4['section']})")

    banner(5, "withdraw only ONE of three carried sections")
    fresh()
    m5 = instrument.Meter()
    s5 = reuse.ReuseStore()
    a5 = reference.answer(Q_MULTI, tech, p, m5)
    s5.retain(Q_MULTI, [corpus.SECTIONS[i] for i in a5["sections"]], a5["text"], m5)
    print(f"    the retained answer carries {len(a5['sections'])} sections: {a5['sections']}")
    corpus.DOCUMENTS["D-102"].state = "WITHDRAWN"
    out5 = s5.serve(Q_MULTI, tech, m5)
    print(f"    withdrawing only D-102 → served={out5['served']}")
    print(f"    refused because of: {out5['section']}")
    print()
    print("    A design that re-checked only the FIRST section would have served a withdrawn step here.")

    banner(6, "what did we save, and what did we keep?")
    fresh()
    m_base = instrument.Meter()
    reference.answer(Q, tech, p, m_base)
    reference.answer(Q, tech, p, m_base)
    m_opt = instrument.Meter()
    s6 = reuse.ReuseStore()
    f6 = reference.answer(Q, tech, p, m_opt)
    s6.retain(Q, [corpus.SECTIONS[i] for i in f6["sections"]], f6["text"], m_opt)
    s6.serve(Q, tech, m_opt)
    b, o = m_base.consumption(), m_opt.consumption()
    print("    two requests, reference path : " + "  ".join(
        f"{k}={b.get(k, 0)}" for k in ("generation_calls", "retrieval_calls", "authority_confirmations")))
    print("    two requests, with reuse     : " + "  ".join(
        f"{k}={o.get(k, 0)}" for k in ("generation_calls", "retrieval_calls", "authority_confirmations")))
    print("    preservation work introduced : " + "  ".join(
        f"{k}={o.get(k, 0)}" for k in ("metadata_writes", "equivalence_checks")))
    print()
    print("    THE POINT OF THE LAB")
    print("      The saving is real: a generation call and a retrieval disappeared.")
    print("      The correctness machinery is also real: carriage, an equivalence check, and an")
    print("      authority confirmation for EVERY carried section, on EVERY serve.")
    print("      Notice what did NOT fall: authority_confirmations is the same in both rows.")
    print("      Reuse removed the generation and the retrieval. It did not remove the obligation")
    print("      to confirm, on every serve, that every carried section is still authorised and")
    print("      still in force. That work is why the reuse is allowed to happen at all.")
    print("      An honest comparison subtracts the second from the first. A comparison that counts")
    print("      only the generation call you removed will always make reuse look better than it is.")
    print()
    print("    WHAT THIS LAB DOES NOT SHOW YOU")
    print("      It does not show that reuse pays. That depends on how repetitive real traffic is,")
    print("      on real prices, and on how stable the measurement is — none of which this lab")
    print("      measures. The repetition you just saw is SYNTHETIC: it was written to create a")
    print("      reuse opportunity, not observed in production.")
    print("      Episode 05's own economic finding was:")
    print("        COST-004 = NOT EMPIRICALLY RESOLVED IN THIS EPISODE")
    print("      Fewer calls is an ACCOUNTING result. It is not a proven monetary saving.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
