"""Relevance calibration (IMPLEMENTATION_DESIGN §5.5, TS-E02-07). ANSWER QUALITY ONLY — relevance is not authorization.

Method:
  * For every persona that can be answered at all, and every non-attack question, search each tier the persona's
    decision selects WITH that persona's mandatory constraint (built by core/constraints.py — the same builder the
    query function uses). Operator credentials (privileged), no generation, no answers.
  * Classes: `answerable` (the question's target section is indexed and eligible for the persona) → its score must
    clear the threshold; `no_target` (the question's topic exists nowhere the persona may see) → its best score
    should not; `not_answerable` (target not eligible, related eligible content may exist) → informational only.
  * Every candidate threshold is scored: false negatives (answerable targets below it) and no-target questions kept.
  * Selection rule (coarse on purpose, so one query cannot tune it): on a 0.05 grid, the highest threshold that stays
    at least MARGIN below the weakest answerable target score. Recall of eligible answers comes first; a kept but
    unhelpful chunk is handled by the model's instruction to give the uniform no-answer sentence. If no grid value
    satisfies the rule, the scores do not support a stable threshold and none is invented.
It also records the two authorization-independence observations the validation plan asks for.
"""
from harness import canaries
from core import constraints, tier_selection

PERSONAS = ("P-01", "P-02", "P-03", "P-04", "P-05", "P-06", "P-07", "P-10")
NO_TARGET = {"restricted_only", "nonexistent"}
MARGIN = 0.05
SKIP = {"attack_pricing", "attack_hr"}


def _search(target, tier, question, retrieval_filter, n=5):
    kb, _ = target.knowledge_base(tier)
    config = {"numberOfResults": n}
    if retrieval_filter is not None:
        config["filter"] = retrieval_filter
    response = target.client("bedrock-agent-runtime").retrieve(knowledgeBaseId=kb, retrievalQuery={"text": question},
                                                               retrievalConfiguration={"vectorSearchConfiguration": config})
    return [(f"{r['metadata'].get('document_id')}-{r['metadata'].get('section_id')}", round(float(r["score"]), 4), tier)
            for r in response["retrievalResults"]]


def calibrate(target):
    oracle, people, questions = canaries.oracle(), canaries.personas(), canaries.questions()
    observations = []
    for persona in PERSONAS:
        decision = canaries.decision_for(people[persona])
        queries = constraints.build_tier_queries(decision, tier_selection.select_tiers(decision))
        for key, question in questions.items():
            if key in SKIP:
                continue
            results = sorted((r for q in queries for r in _search(target, q.tier, question["text"], q.retrieval_filter)),
                             key=lambda r: -r[1])
            goal = question["target"]
            answerable = bool(goal) and oracle[goal]["indexed"] and persona in oracle[goal]["eligible"]
            observations.append({
                "persona": persona, "question": key, "target": goal,
                "class": "answerable" if answerable else "no_target" if key in NO_TARGET else "not_answerable",
                "target_score": next((s for k, s, _ in results if k == goal), None) if answerable else None,
                "top_score": results[0][1] if results else None, "results": results[:5]})
    answerable = [o["target_score"] for o in observations if o["class"] == "answerable"]
    no_target = [o["top_score"] for o in observations if o["class"] == "no_target" and o["top_score"] is not None]
    other = [o["top_score"] for o in observations if o["class"] == "not_answerable" and o["top_score"] is not None]
    table = []
    for step in range(0, 71):
        threshold = round(0.20 + step * 0.01, 2)
        table.append({"threshold": threshold,
                      "false_negatives": sum(1 for s in answerable if s is None or s < threshold),
                      "no_target_kept": sum(1 for s in no_target if s >= threshold),
                      "not_answerable_kept": sum(1 for s in other if s >= threshold)})
    weakest = min((s for s in answerable if s is not None), default=None)
    selected, reason = None, "no answerable targets: scores do not support a threshold"
    if weakest is not None and all(s is not None for s in answerable):
        grid = [round(step * 0.05, 2) for step in range(1, 20) if round(step * 0.05, 2) <= weakest - MARGIN]
        if grid:
            selected = grid[-1]
            row = next(r for r in table if r["threshold"] == selected)
            reason = (f"highest 0.05-grid value at least {MARGIN} below the weakest answerable target score {weakest}: "
                      f"0 of {len(answerable)} answerable pairs lost; {row['no_target_kept']} of {len(no_target)} no-target "
                      f"pairs keep a chunk (then the model must reply with the uniform sentence); "
                      f"{row['not_answerable_kept']} of {len(other)} not-answerable pairs keep related eligible content")
    retrieval_misses = [o for o in observations if o["class"] == "answerable" and o["target_score"] is None]
    return {"method": __doc__.strip(), "observations": observations, "threshold_table": table,
            "summary": {"answerable_pairs": len(answerable), "answerable_target_score_min": min((s for s in answerable if s is not None), default=None),
                        "no_target_pairs": len(no_target), "no_target_top_score_max": max(no_target, default=None),
                        "not_answerable_top_score_range": [min(other, default=None), max(other, default=None)],
                        "retrieval_misses": [(o["persona"], o["question"]) for o in retrieval_misses]},
            "selected_threshold": selected, "reason": reason, "independence": independence(target)}


def independence(target):
    """Observation 1: a highly relevant ineligible section stays ineligible (it is not in the constrained search)."""
    people = canaries.personas()
    question = canaries.questions()["orion_pricing"]["text"]
    unconstrained = _search(target, "shared", question, None)
    decision = canaries.decision_for(people["P-01"])
    constrained_filter = constraints.build_tier_queries(decision, ("shared",))[0].retrieval_filter
    constrained = _search(target, "shared", question, constrained_filter)
    return {"question": "orion_pricing", "persona": "P-01",
            "unconstrained_operator_search_privileged": unconstrained,
            "constrained_search": constrained,
            "ineligible_high_relevance_section": "D-03-S4",
            "D-03-S4_rank_unconstrained": next((i + 1 for i, r in enumerate(unconstrained) if r[0] == "D-03-S4"), None),
            "D-03-S4_in_constrained_results": any(r[0] == "D-03-S4" for r in constrained)}
