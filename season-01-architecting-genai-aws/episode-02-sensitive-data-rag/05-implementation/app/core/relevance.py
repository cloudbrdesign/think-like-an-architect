"""Relevance (IMPLEMENTATION_DESIGN §5.5, TS-E02-07). ANSWER QUALITY ONLY.

    RELEVANCE IS NOT AUTHORIZATION.

It decides "is this ELIGIBLE, VERIFIED chunk useful enough to answer with?" — never "may this requester see it?".
That is why this function receives only chunks that already passed verification, and never the decision, labels or
scopes: it cannot make an ineligible chunk eligible, and omitting a low-scoring chunk does not change its authorization
status. The threshold is calibrated on the synthetic corpus (see 07-evidence, relevance calibration).
"""

MAX_CONTEXT_CHUNKS = 5


def apply(verified_chunks, min_score):
    """Return (kept, omitted): chunks scoring at least `min_score`, best first, at most MAX_CONTEXT_CHUNKS."""
    ranked = sorted(verified_chunks, key=lambda c: (-float(c.score), c.chunk_id))
    kept = [c for c in ranked if float(c.score) >= float(min_score)][:MAX_CONTEXT_CHUNKS]
    kept_ids = {c.chunk_id for c in kept}
    return tuple(kept), tuple(c for c in ranked if c.chunk_id not in kept_ids)
