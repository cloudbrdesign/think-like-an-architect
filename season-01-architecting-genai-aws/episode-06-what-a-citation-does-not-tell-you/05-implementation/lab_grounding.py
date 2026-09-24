#!/usr/bin/env python3
"""Episode 06 lab — what a citation does not tell you.

Runs locally in seconds. No AWS account, no API key, no model call, no cost.

This lab reproduces the evidence that PREVENTED an architecture decision. It does not implement one.
"""
import argparse
import sys

from core import cases, controls, corpus, extraction, segmentation

RULE = "─" * 74


def head(n, title):
    print(f"\n{RULE}\n  STEP {n} — {title}\n{RULE}")


def show_procedure():
    head(1, "the authority everything is judged against")
    print(f"    {corpus.DOC} — {corpus.TITLE}\n")
    for sid, s in corpus.SECTIONS.items():
        gov = corpus.governors(sid)
        tag = f"   (limited by {', '.join(gov)})" if gov else ""
        print(f"    {sid}  {s['heading']:<26} {s['text']}{tag}")
    print("\n    Read D-204#3 twice. It is the only section that is not an instruction.")


def show_controls():
    head(2, "the controls Episodes 01-03 put in front of every answer")
    for name, why in controls.RUNGS:
        mark = "  (this system cannot decide this)" if name == "claim_supported_by_section" else ""
        print(f"    {name:<30} {why}{mark}")


def run_case(key, reveal):
    c = cases.CASES[key]
    r, green = controls.run(cases.PRINCIPAL, c["cites"], cases.RETRIEVED)
    print(f"\n    question : {c['question']}")
    print(f"    answer   : {c['answer']}")
    print(f"    cites    : {', '.join(c['cites'])}")
    print("\n    controls:")
    for name, _ in controls.RUNGS:
        v = r[name]
        print(f"      {name:<30} {'PASS' if v else 'FAIL' if v is False else 'NOT DECIDABLE'}")
    print(f"      {'operational health':<30} {'all green' if all(controls.health().values()) else 'degraded'}")
    print(f"\n    every decidable control: {'ALL GREEN' if green else 'NOT ALL GREEN'}")
    print("\n    now read the cited section yourself:")
    for s in c["cites"]:
        print(f"      {s}  \"{corpus.text(s)}\"")
    print(f"      claim    \"{c['claim']}\"")
    if reveal:
        print(f"\n    what the procedure actually carries: {c['expected']}")
        print(f"      {c['note']}")
    else:
        print("\n    Decide for yourself before re-running with --reveal.")
    return green, c["expected"]


def exercise_c2(reveal):
    head(3, "the normal case")
    run_case("normal", reveal)
    head(4, "the same controls, a different instruction")
    green, expected = run_case("quiet", reveal)
    head(5, "two more, same shape")
    run_case("related", reveal)
    run_case("applicability", reveal)
    print("\n    In every case above the controls returned the same verdict.")
    print("    They established who asked, what they may see, whether it is current, whether the")
    print("    section was retrieved and whether the citation resolves. Not one of them read the answer.")
    return green


def exercise_c11(reveal):
    head(6, "what counts as one claim?")
    print(f"\n    answer : {segmentation.ANSWER}")
    print(f"    cites  : {', '.join(segmentation.CITES)}")
    for s in segmentation.CITES:
        print(f"      {s}  \"{corpus.text(s)}\"")
    outcomes = {}
    for name, claims in segmentation.BOUNDARIES.items():
        served = segmentation.serve(claims)
        outcomes[name] = served
        print(f"\n    {name}")
        for cl in claims:
            print(f"      carried={cl['carried_by_cited_section']:<9} {cl['claim']}")
            print(f"        {cl['why']}")
        print(f"      -> the control would {'SERVE' if served else 'REFUSE'} this answer")
    flipped = len(set(outcomes.values())) > 1
    print(f"\n    same answer · same citation · same procedure · decision changed: {flipped}")
    if reveal:
        print("\n    Nothing above was caused by entitlement, currency, retrieval, a broken citation")
        print("    or malformed data. It was caused by the boundary used to decide what one claim is —")
        print("    the unit the proposed control is supposed to protect.")
    return flipped


def extension(reveal):
    head(7, "OPTIONAL — falsifying a candidate architecture (not the answer)")
    print("\n    Candidate: stop asserting instructions; quote the procedure instead.")
    print("    NOT SELECTED. Here are three ways quoting alone still fails.\n")
    for name, p in extraction.PROBES.items():
        found = extraction.problems(p["cites"], p["framing"])
        print(f"    {name}")
        print(f"      renders: {extraction.render(p['cites'], p['framing'])}")
        for f in found:
            print(f"      PROBLEM  {f}")
        if not found:
            print("      no problem found in this probe")
        if reveal:
            print(f"      notice:  {p['what_to_notice']}")
        print()


def questions():
    head(8, "the architecture questions")
    for q in [
        "What did every inherited control successfully establish?",
        "What did none of them establish?",
        "Why was the citation insufficient?",
        "What exactly is the unit of enforcement you would protect?",
        "Why did the serve decision change under another defensible segmentation?",
        "What additional evidence would you require before selecting serve-time verification?",
        "What would you need to establish before calling a second verifier independent?",
        "Which architecture option can you defend from the evidence you currently have?",
    ]:
        print(f"    - {q}")
    print("\n    On the last question, this is a complete and successful answer when you can defend it:")
    print("      THE EVIDENCE DOES NOT SUPPORT SELECTING ONE YET.")
    print("\n    That is the conclusion this engagement reached. No architecture was selected.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--reveal", action="store_true",
                    help="show what the procedure carries, and the commentary")
    ap.add_argument("--extension", action="store_true", help="run the optional Option-5 falsification")
    a = ap.parse_args()
    problems = cases.fixture_consistency(corpus)
    if problems:
        print("FIXTURE INCONSISTENT - this lab cannot demonstrate what it claims:")
        for pr in problems:
            print(f"  - {pr}")
        print("Restore core/corpus.py and core/cases.py to their published state.")
        return 2
    show_procedure()
    show_controls()
    green = exercise_c2(a.reveal)
    flipped = exercise_c11(a.reveal)
    if a.extension:
        extension(a.reveal)
    questions()
    print(f"\n{RULE}")
    print("  This lab reproduces the evidence that prevented an architecture decision.")
    print("  It does not implement the Episode 06 architecture, because there is not one.")
    print(f"{RULE}")
    return 0 if (green and flipped) else 1


if __name__ == "__main__":
    sys.exit(main())
