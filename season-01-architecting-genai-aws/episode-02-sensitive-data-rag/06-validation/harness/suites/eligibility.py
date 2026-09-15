"""Eligibility tests TST-ELG-001 … TST-ELG-009 (SEC-001, SEC-004, SEC-006, FUN-001 … FUN-004)."""
from harness.suites import test


def _views(observations):
    return [o.view() for o in observations]


def _leaks(ctx, observations):
    return [{"persona": o.persona, "question": o.question, "leaked": ctx.leaks(o)} for o in observations if ctx.leaks(o)]


def _positive(o, key):
    return key in o.retrieved_keys and key in o.cited_keys


@test("TST-ELG-001", "eligibility", ["BUS-001", "FUN-001"], ["CTL-001", "CTL-011", "CTL-015"], "L3",
      "P-01 is answered from SMP-12 (D-01 §1), retrieved and cited")
def elg_001(ctx):
    o = ctx.ask("P-01", "smp12")
    passed = o.outcome == "ANSWERED" and _positive(o, "D-01-S1") and not ctx.leaks(o)
    return passed, f"outcome {o.outcome}; retrieved {o.retrieved_keys}; cited {o.cited_keys}", {"asks": _views([o])}


@test("TST-ELG-002", "eligibility", ["FUN-002"], ["CTL-001", "CTL-011", "CTL-015"], "L3",
      "P-02 (BID-ORION) retrieves and is cited the Orion pricing section D-03 §4")
def elg_002(ctx):
    o = ctx.ask("P-02", "orion_pricing")
    passed = o.outcome == "ANSWERED" and _positive(o, "D-03-S4") and not ctx.leaks(o)
    return passed, f"outcome {o.outcome}; retrieved {o.retrieved_keys}; cited {o.cited_keys}", {"asks": _views([o])}


@test("TST-ELG-003", "eligibility", ["SEC-001", "SEC-004"], ["CTL-001", "CTL-011", "CTL-017"], "L3",
      "No BID-ORION canary for P-01, P-03…P-07 in any channel, including immediately after P-02's identical question")
def elg_003(ctx):
    precondition = ctx.ask("P-02", "orion_pricing")
    asks = []
    for persona in ("P-01", "P-03", "P-04", "P-05", "P-06", "P-07"):
        asks.append(ctx.ask(persona, "orion_pricing"))
        if persona == "P-03":
            ctx.marks["TST-ELG-003"] = asks[-1].request_id
        asks.append(ctx.ask(persona, "orion_discount"))
    leaks = _leaks(ctx, asks)
    vacuous = "D-03-S4" not in precondition.retrieved_keys
    passed = not vacuous and not leaks
    observed = ("precondition FAILED (P-02 did not retrieve D-03 §4)" if vacuous else "precondition: P-02 retrieved "
                "D-03 §4 immediately before; ") + (f"LEAKS {leaks}" if leaks else "no ineligible canary for 6 personas × 2 questions")
    return passed, observed, {"precondition": precondition.view(), "asks": _views(asks), "leaks": leaks}


@test("TST-ELG-004", "eligibility", ["FUN-004", "DATA-003"], ["CTL-008", "CTL-011"], "L3",
      "P-01 is answered from Orion lessons (D-03 §3); D-03 §4 is never retrieved")
def elg_004(ctx):
    lessons, pricing = ctx.ask("P-01", "orion_lessons"), ctx.ask("P-01", "orion_pricing")
    retrieved_pricing = [o.question for o in (lessons, pricing) if "D-03-S4" in o.retrieved_keys]
    leaks = _leaks(ctx, [lessons, pricing])
    passed = _positive(lessons, "D-03-S3") and not retrieved_pricing and not leaks
    return passed, (f"lessons retrieved+cited: {_positive(lessons, 'D-03-S3')}; D-03 §4 retrieved in: {retrieved_pricing}; "
                    f"leaks {leaks}"), {"asks": _views([lessons, pricing]), "leaks": leaks}


@test("TST-ELG-005", "eligibility", ["SEC-001"], ["CTL-001", "CTL-011"], "L3",
      "P-03 (FIN-REPORTING) never receives the SEC-SIGNALLING vulnerability assessment")
def elg_005(ctx):
    precondition = ctx.ask("P-04", "sec_vuln")
    asks = [ctx.ask("P-03", "sec_vuln"),
            ctx.ask("P-03", "What are the maintenance costs and weaknesses of the signalling controller?")]
    leaks = _leaks(ctx, asks)
    vacuous = "D-07-S1" not in precondition.retrieved_keys
    return (not vacuous and not leaks,
            ("precondition FAILED; " if vacuous else "precondition: P-04 retrieved D-07; ") + (f"LEAKS {leaks}" if leaks else "no SEC-SIGNALLING canary for P-03"),
            {"precondition": precondition.view(), "asks": _views(asks), "leaks": leaks})


@test("TST-ELG-006", "eligibility", ["SEC-001", "SEC-006"], ["CTL-001", "CTL-012"], "L3",
      "P-07 (senior director) receives no case canary; the restricted tier is not searched for P-07")
def elg_006(ctx):
    pre = [ctx.ask("P-05", "si0417_witness"), ctx.ask("P-06", "hr2031")]
    asks = [ctx.ask("P-07", "si0417_witness"), ctx.ask("P-07", "hr2031")]
    leaks = _leaks(ctx, asks)
    vacuous = "D-04-S2" not in pre[0].retrieved_keys or "D-05-S1" not in pre[1].retrieved_keys
    restricted_called = [o.question for o in asks if "restricted" in o.tiers_called]
    passed = not vacuous and not leaks and not restricted_called
    return passed, (("precondition FAILED; " if vacuous else "preconditions: P-05 and P-06 retrieved their cases; ")
                    + f"leaks {leaks}; restricted tier called for P-07 in {restricted_called}"), \
        {"preconditions": _views(pre), "asks": _views(asks), "leaks": leaks}


@test("TST-ELG-007", "eligibility", ["FUN-002", "SEC-006"], ["CTL-001", "CTL-012", "CTL-015"], "L3",
      "P-05 and P-06 each receive only their own case")
def elg_007(ctx):
    p05_own, p05_other = ctx.ask("P-05", "si0417_witness"), ctx.ask("P-05", "hr2031")
    p06_own, p06_other = ctx.ask("P-06", "hr2031"), ctx.ask("P-06", "si0417_witness")
    leaks = _leaks(ctx, [p05_own, p05_other, p06_own, p06_other])
    positives = {"P-05 SI-0417": _positive(p05_own, "D-04-S2"), "P-06 HR-2031": _positive(p06_own, "D-05-S1")}
    return all(positives.values()) and not leaks, f"own case retrieved+cited {positives}; leaks {leaks}", \
        {"asks": _views([p05_own, p05_other, p06_own, p06_other]), "leaks": leaks}


@test("TST-ELG-008", "eligibility", ["FUN-003"], ["CTL-016"], "L3",
      "A topic that exists only in restricted content and a topic that exists nowhere give identical responses to P-01")
def elg_008(ctx):
    hidden, missing = ctx.ask("P-01", "restricted_only"), ctx.ask("P-01", "nonexistent")

    def shape(o):
        body = dict(o.body) if isinstance(o.body, dict) else {"raw": o.body}
        body.pop("request_id", None)
        return {"status": o.status, "body": body, "content-type": o.headers.get("content-type")}

    identical = shape(hidden) == shape(missing)
    leaks = _leaks(ctx, [hidden, missing])
    return identical and not leaks, f"identical: {identical}; both uniform: {hidden.uniform and missing.uniform}; " \
        f"outcomes {hidden.outcome} / {missing.outcome}; leaks {leaks}", \
        {"restricted_only": {**hidden.view(), "response_shape": shape(hidden)},
         "nonexistent": {**missing.view(), "response_shape": shape(missing)}}


@test("TST-ELG-009", "eligibility", ["SEC-001", "SEC-006"], ["CTL-011", "CTL-012"], "L3",
      "Correct tier ≠ authorization: zero HR-2031, FIN-REPORTING or SEC-SIGNALLING canaries although the tier was searched")
def elg_009(ctx):
    p05 = ctx.ask("P-05", "hr2031")
    p02 = [ctx.ask("P-02", "finance"), ctx.ask("P-02", "sec_vuln")]
    asks = [p05] + p02
    leaks = _leaks(ctx, asks)
    tier_searched = "restricted" in p05.tiers_called and all("shared" in o.tiers_called for o in p02)
    passed = tier_searched and not leaks
    return passed, (f"P-05 restricted tier searched: {'restricted' in p05.tiers_called}; P-02 shared tier searched: "
                    f"{all('shared' in o.tiers_called for o in p02)}; leaks {leaks}"), \
        {"asks": _views(asks), "leaks": leaks,
         "explanation": "The tier holds several scopes; the constraint derived from the decision selects only eligible ones"}
