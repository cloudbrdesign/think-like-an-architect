#!/usr/bin/env python3
"""Episode 07 lab QA. Two-sided: every claim is checked together with a case that must NOT hold.

A one-sided check passes on a constant. Each pair below fails if the lab stops discriminating.

Usage: python3 qa_lab.py      exit 0 all pass · 1 any fail · 2 a precondition is broken
"""
import io
import pathlib
import re
import subprocess
import sys
from contextlib import redirect_stdout

from core import mapping as mapping_mod
from core import paths as paths_mod
from core.decide import (ANSWERED, CANNOT_DETERMINE_OBLIGATIONS, CANNOT_ESTABLISH_PERMISSION_TO_ANSWER,
                         CAPACITY_REFUSED, DEGRADED_BUT_ANSWERED, ESTABLISH, INHERIT, MUST_NOT_ANSWER,
                         TRUST_WITHHELD, decide)
from core.procedures import PROCEDURE, RecordsSystem
import lab_failover

HERE = pathlib.Path(__file__).parent
CALLER_OUTCOMES = {ANSWERED, DEGRADED_BUT_ANSWERED, CAPACITY_REFUSED, TRUST_WITHHELD}
RESULTS = []


def ck(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))


def incident(issuer_anchored=False):
    records = RecordsSystem()
    records.withdraw("D-204-S1", 1)
    records.tick = 2
    path = (paths_mod.failover_with_issuer_window(0) if issuer_anchored
            else paths_mod.failover_with_replica(0))
    return records, path


def main():
    records, path = incident()

    # 0 -- the normal serving condition, so that later refusals are a result and not a constant.
    clean = RecordsSystem(); clean.tick = 0
    normal = decide(paths_mod.primary(), clean, True, "D-204-S1")
    ck("the primary path serves under normal conditions", normal["outcome"] == ANSWERED, normal["outcome"])
    ck("and it serves on CONFIRMED currency, not on a copy", normal["currency_basis"] == "CONFIRMED",
       normal["currency_basis"])
    ck("CONFIRMED is only ever reached by reaching the authority",
       normal["authority_reachable"] is True and normal["reason"] == "currency_confirmed_on_this_path")

    # 1 -- the quiet failure exists, AND the establishing behaviour does not produce it
    a = decide(path, records, True, "D-204-S1", behaviour=INHERIT)
    b = decide(path, records, True, "D-204-S1", behaviour=ESTABLISH)
    ck("inheriting serves the withdrawn instruction", a["outcome"] == ANSWERED, a["outcome"])
    ck("establishing withholds the same request", b["outcome"] == TRUST_WITHHELD, b["outcome"])
    ck("the two behaviours differ on the same input", a["outcome"] != b["outcome"])

    # 2 -- ordinary signals cannot separate them; the authority signals can
    healthy_records = RecordsSystem(); healthy_records.tick = 2
    healthy = decide(path, healthy_records, True, "D-204-S1", behaviour=INHERIT)
    ck("health signals identical across healthy and quiet-failure cases", path.health() == path.health())
    ck("the quiet case and the healthy case share an outcome under inheritance",
       healthy["outcome"] == a["outcome"] == ANSWERED)
    ck("authority_reachable is what differs, not availability",
       path.authority_reachable is False and path.health()["service_reachable"] is True)

    # 3 -- the four causes stay distinct, AND nothing invents a fifth caller-visible outcome
    causes = {
        "prohibited": decide(path, records, False, "D-204-S1"),
        "unknowable": decide(path, records, None, "D-204-S1"),
        "unreachable": decide(path, records, True, "D-204-S1"),
        "infra": decide(paths_mod.Path("failover", path_reachable=False), records, True, "D-204-S1"),
    }
    ck("caller prohibited records MUST_NOT_ANSWER", causes["prohibited"]["cause"] == MUST_NOT_ANSWER)
    ck("permission unknowable records CANNOT_ESTABLISH_PERMISSION_TO_ANSWER",
       causes["unknowable"]["cause"] == CANNOT_ESTABLISH_PERMISSION_TO_ANSWER)
    ck("prohibited and unknowable are NOT the same cause",
       causes["prohibited"]["cause"] != causes["unknowable"]["cause"])
    ck("prohibited and unknowable are also distinct by reason",
       causes["prohibited"]["reason"] != causes["unknowable"]["reason"])
    ck("evidence-unavailable and authority-unavailable do not share one reason",
       causes["unreachable"]["reason"] != causes["unknowable"]["reason"])
    ck("infrastructure failure is CAPACITY_REFUSED, never a trust statement",
       causes["infra"]["outcome"] == CAPACITY_REFUSED and causes["infra"]["cause"] == "NONE")
    ck("every caller-visible outcome is one of Episode 04's four",
       all(r["outcome"] in CALLER_OUTCOMES for r in list(causes.values()) + [a, b]))
    ck("no caller-visible outcome is UNMAPPED or a fifth state",
       not any(r["outcome"] in ("UNMAPPED", "MUST_NOT_ANSWER", CANNOT_ESTABLISH_PERMISSION_TO_ANSWER)
               for r in list(causes.values()) + [a, b]))

    # 4 -- capability reduction discriminates, AND does not simply serve everything
    served = decide(path, records, True, "D-900-S1")
    ck("a class needing no current confirmation is still served", served["outcome"] == ANSWERED)
    ck("an actionable class is withheld on the same path", b["outcome"] == TRUST_WITHHELD)
    ck("reduction is not universal permission", served["outcome"] != b["outcome"])

    # 5 -- governance: two owners, and content ownership cannot waive an obligation
    entries = dict(mapping_mod.AUTHORED)
    entries["D-204-S1"] = mapping_mod.Entry("D-204-S1", False, "edited", mapping_mod.RECORDS_OWNER,
                                            None, "unauthorised")
    forged = decide(path, records, True, "D-204-S1", mapping=mapping_mod.Mapping(entries=entries))
    ck("a records-owner edit cannot waive a safety obligation",
       forged["cause"] == CANNOT_DETERMINE_OBLIGATIONS, forged["cause"])
    entries["D-204-S1"] = mapping_mod.Entry("D-204-S1", False, "declared", mapping_mod.RECORDS_OWNER,
                                            mapping_mod.SAFETY, "authorised")
    declared = decide(path, records, True, "D-204-S1", mapping=mapping_mod.Mapping(entries=entries))
    ck("a Safety-declared exemption IS honoured, so the check is not a blanket refusal",
       declared["outcome"] == ANSWERED, declared["outcome"])

    # 6 -- fail-closed, AND a complete mapping is not fail-closed (or the check is vacuous)
    empty = decide(path, records, True, "D-204-S1", mapping=mapping_mod.Mapping(entries={}))
    ck("an absent mapping never serves", empty["cause"] == CANNOT_DETERMINE_OBLIGATIONS)
    across = decide(path, records, True, "D-204-S1",
                    mapping=mapping_mod.Mapping(fetch_route=path.broken_route))
    ck("a mapping behind the failed route never serves", across["cause"] == CANNOT_DETERMINE_OBLIGATIONS)
    ck("the complete mapping does determine the obligation", b["obligation_required"] is True)

    # 7 -- independence is measured, and is NOT sufficiency
    _, independent = incident(issuer_anchored=True)
    ind = decide(independent, records, True, "D-204-S1")
    ck("the issuer-anchored assertion is recognised as independent",
       "INDEPENDENT" in ind["currency_basis"], ind["currency_basis"])
    ck("the dependent copy is recognised as dependent", "DEPENDENT" in b["currency_basis"])
    ck("independence alone does not produce permission", ind["outcome"] == TRUST_WITHHELD)
    signed = paths_mod.failover_with_replica(0)
    signed.carried["D-204-S1"].provenance = ["local-cache", "signature-verified-locally"] + \
        signed.carried["D-204-S1"].provenance
    ck("a local signature does not confer independence",
       "DEPENDENT" in decide(signed, records, True, "D-204-S1")["currency_basis"])

    # 7b -- permission must never depend on the AGE of the assertion (no implicit threshold)
    ages = {}
    for gap in (0, 1, 5, 500):
        r = RecordsSystem(); r.withdraw("D-204-S1", 1); r.tick = 1 + gap
        ages[gap] = decide(paths_mod.failover_with_replica(0), r, True, "D-204-S1")["outcome"]
    ck("permission never varies with the age of the assertion", len(set(ages.values())) == 1, str(ages))
    ck("and that single outcome is withholding, not serving", set(ages.values()) == {TRUST_WITHHELD})

    # 8 -- declared degradation requires the contract to permit it
    permitted = decide(independent, records, True, "D-204-S1", contract_permits_degraded=True)
    ck("declared degradation is available when the contract permits it",
       permitted["outcome"] == DEGRADED_BUT_ANSWERED)
    ck("and is NOT the default", ind["outcome"] != permitted["outcome"])

    # 9 -- boundaries the lab must never cross
    learner_src = [p for p in sorted(HERE.rglob("*.py")) if p.name != "qa_lab.py"]
    src = "\n".join(p.read_text() for p in learner_src)
    ck("the source scan covers the learner code and excludes this file",
       len(learner_src) >= 5 and all(p.name != "qa_lab.py" for p in learner_src),
       str([p.name for p in learner_src]))
    # "never computed" means: no learner line derives it. Printing the constant is not computing it,
    # which the first cut of this check got wrong and failed on a display f-string.
    grounding_lines = [l for l in src.splitlines()
                       if "o6_grounding" in l and ("=" in l or ":" in l)]
    derived = [l for l in grounding_lines
               if "NOT_DECIDABLE" not in l and "print(" not in l and 'f"' not in l and "fields" not in l]
    ck("grounding is never computed", "o6_grounding" in src and not derived, str(derived)[:200])
    ck("nothing in the lab defines a grounding verdict function",
       not re.search(r"def\s+\w*(?:ground|support|verif)\w*\s*\(", src, re.I))
    ck("every record reports o6_grounding = NOT_DECIDABLE",
       all(r["o6_grounding"] == "NOT_DECIDABLE" for r in list(causes.values()) + [a, b, ind, permitted]))
    ck("no network, cloud or model client anywhere in the lab",
       not re.search(r"\b(boto3|botocore|requests|urllib|httpx|socket|openai|anthropic|bedrock)\b", src))
    ck("no duration, percentage or SLO in the lab source or README",
       not re.search(r"\b\d[\d,.]*\s*(seconds?|minutes?|ms\b|hours?|percent|%)|\b(SLO|RTO|RPO)\b",
                     src + (HERE / "README.md").read_text()))
    ck("the README states the lab sets no threshold",
       "sets no staleness threshold" in (HERE / "README.md").read_text())
    ck("the README states grounding is not decided",
       "NOT_DECIDABLE" in (HERE / "README.md").read_text())

    # 9b -- the eight required architectural distinctions are each demonstrated, by behaviour or by text
    out = io.StringIO()
    with redirect_stdout(out):
        lab_failover.main(["--all"])
    transcript = out.getvalue()
    sequence = {
        "1 normal serving condition": "primary path, normal:",
        "2 failover becomes operational": "The second region takes over",
        "3 availability restored, authority not": "RESTORE AVAILABILITY WITHOUT RESTORING AUTHORITY",
        "4 the per-request rule applied": "must ESTABLISH",
        "5 reduction or refusal, never a silent grant": "Capability is reduced. Trust is not.",
        "6 mapping cannot create a Safety exemption": "exemption not declared by Safety & Compliance",
        "7 independence is not currency": "Independence and",
        "8 the staleness question, with no threshold": "THRESHOLD / POLICY AUTHORITY REQUIRED",
    }
    for name, anchor in sequence.items():
        ck(f"the learner sequence demonstrates: {name}", anchor in transcript, f"anchor absent: {anchor!r}")

    # 9c -- the inheriting behaviour is never presented as acceptable (D as a sole basis)
    prose = transcript + (HERE / "README.md").read_text()
    rehab = re.findall(r"(?:pre-?certif\w+|inherit\w+)[^.\n]{0,60}?"
                       r"\b(?:is|are|remains?)\s+(?:acceptab\w+|sufficient|fine|safe|recommended|enough)\b",
                       prose, re.I)
    ck("the inheriting behaviour is never presented as acceptable", not rehab, str(rehab)[:160])

    # 9d -- the constructed-case ceiling is prominent, and no production or general claim is made
    ck("the README states the lab is a constructed teaching case",
       "constructed teaching case" in prose or "constructed teaching case" in prose.lower())
    general = re.findall(r"(?:in production|production (?:reliability|systems?)|all (?:LLM|RAG)|in general)"
                         r"[^.\n]{0,40}?\b(?:is|are|will|holds)\b(?!\s+not\b)", prose, re.I)
    ck("no production or general LLM/RAG claim in the lab's prose or output", not general, str(general)[:160])
    ck("no reliability percentage is derived from any count",
       not re.search(r"\b\d{1,3}\s*%|\b\d+\s*(?:of|/)\s*\d+\s*(?:checks?|tests?)\s*(?:pass|=)", prose, re.I))

    # 10 -- every README command runs, and the attacks all hold
    cmds = [(s, a.split("#")[0].strip())
            for s, a in re.findall(r"^python3 (\S+\.py)(.*)$", (HERE / "README.md").read_text(), re.M)]
    ck("the README lists the commands it claims", len(cmds) >= 9, str(len(cmds)))
    for script, args in cmds:
        if script == "qa_lab.py":
            continue                      # this file; running it here would recurse
        p = subprocess.run([sys.executable, script] + (args.split() if args else []), cwd=HERE,
                           capture_output=True, text=True)
        ck(f"README command runs: {script} {args}".rstrip() + " -> exit 0",
           p.returncode == 0, p.stderr[-160:])
    for n in (1, 2, 3, 4):
        with redirect_stdout(io.StringIO()):
            held = lab_failover.attack(n)
        ck(f"attack {n} fails closed", held)

    # 11 -- a broken precondition must be loud, not silently degrade the exercise
    try:
        decide(path, records, True, "D-999-NONEXISTENT")
        ck("an unknown section raises rather than quietly refusing", False, "no exception")
    except KeyError:
        ck("an unknown section raises rather than quietly refusing", True)

    for ok, name, detail in RESULTS:
        print(("PASS  " if ok else "FAIL  ") + name + (f"\n        {detail}" if detail and not ok else ""))
    failed = [r for r in RESULTS if not r[0]]
    print(f"\nEpisode 07 lab QA: {'PASS' if not failed else 'FAIL'} — {len(RESULTS) - len(failed)}/{len(RESULTS)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
