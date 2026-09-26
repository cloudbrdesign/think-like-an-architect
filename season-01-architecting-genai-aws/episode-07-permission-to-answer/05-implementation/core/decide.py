"""The decision. This is the architecture the episode arrives at, written as a procedure.

    A failover event does not inherit permission to answer merely because another serving path is
    available. For every obligation required for the request and that we can actually adjudicate, the
    serving path must establish it using authority appropriate to that obligation. If a required
    obligation cannot be established, the system must not silently treat absence of evidence as
    permission: it reduces capability, serves with explicitly declared degraded status where the
    governing contract permits it, or refuses. The resulting state must remain reconstructable.

Two things this module deliberately does NOT do:

  * it never computes whether the answer is CARRIED BY the section it cites. That obligation is
    reported as NOT_DECIDABLE and left to you. Episode 06 could not establish it and this lab does
    not pretend otherwise;
  * it never turns an age into a permission. There is no staleness threshold here, because no one
    with the authority to set one has set one.
"""
from . import mapping as mapping_mod
from .procedures import PROCEDURE

# Episode 04's caller-visible contract, inherited unchanged. Four outcomes, and no fifth.
ANSWERED = "ANSWERED"
DEGRADED_BUT_ANSWERED = "DEGRADED_BUT_ANSWERED"
CAPACITY_REFUSED = "CAPACITY_REFUSED"
TRUST_WITHHELD = "TRUST_WITHHELD"

# The causes underneath it. These are what must stay distinguishable in the record.
MUST_NOT_ANSWER = "MUST_NOT_ANSWER"
CANNOT_ESTABLISH_PERMISSION_TO_ANSWER = "CANNOT_ESTABLISH_PERMISSION_TO_ANSWER"
CANNOT_DETERMINE_OBLIGATIONS = "CANNOT_DETERMINE_OBLIGATIONS"
NO_CAUSE = "NONE"

INHERIT = "inherit"        # pre-event certification only: no act at decision time. The bug.
ESTABLISH = "establish"    # the decision above.


def _record(**kw):
    base = {
        "serving_path": None, "requester": None, "section_id": None,
        "path_reachable": None, "authority_reachable": None,
        "obligation_required": None, "obligation_basis": None,
        "entitlement": None, "currency_basis": None, "currency_detail": None,
        "assertion_provenance": None, "mapping_version": None,
        "outcome": None, "reason": None, "cause": NO_CAUSE,
        "o6_grounding": "NOT_DECIDABLE",
        "boundary": "constructed teaching case; establishes nothing about production, any real model, "
                    "any provider, general LLM/RAG behaviour, people or organisations",
    }
    base.update(kw)
    return base


def decide(path, records, requester_entitled, section_id, *, behaviour=ESTABLISH,
           mapping=None, contract_permits_degraded=False, as_of=None):
    """Serve, reduce, declare or refuse -- and record why, in a form you can reconstruct."""
    if section_id not in PROCEDURE:
        raise KeyError(f"no such section: {section_id}")
    as_of = records.tick if as_of is None else as_of
    mapping = mapping_mod.Mapping() if mapping is None else mapping
    assertion = path.carried.get(section_id)
    rec = _record(serving_path=path.name, requester="depot-technician", section_id=section_id,
                  path_reachable=path.path_reachable, authority_reachable=path.authority_reachable,
                  assertion_provenance=(assertion.provenance if assertion else None),
                  mapping_version=mapping.describe()["version"])

    # 0 -- infrastructure. Distinct from everything below it, and never a trust statement.
    if not path.path_reachable:
        return _record(**{**rec, "outcome": CAPACITY_REFUSED, "reason": "path_unreachable",
                          "cause": NO_CAUSE})

    # 1 -- entitlement: three values, never merged. "We cannot tell" is not "you may not".
    if requester_entitled is False:
        return _record(**{**rec, "entitlement": "DENIED", "outcome": TRUST_WITHHELD,
                          "reason": "entitlement_denied", "cause": MUST_NOT_ANSWER})
    if requester_entitled is None:
        return _record(**{**rec, "entitlement": "NOT_ESTABLISHABLE", "outcome": TRUST_WITHHELD,
                          "reason": "entitlement_not_establishable",
                          "cause": CANNOT_ESTABLISH_PERMISSION_TO_ANSWER})
    rec["entitlement"] = "GRANTED"

    # 2 -- which obligations does this request even require? If that cannot be determined, stop.
    required, basis = mapping.lookup(section_id, broken_route=path.broken_route)
    rec["obligation_required"], rec["obligation_basis"] = required, basis
    if required is None:
        return _record(**{**rec, "outcome": TRUST_WITHHELD, "reason": f"obligation_set_not_determinable:{basis}",
                          "cause": CANNOT_DETERMINE_OBLIGATIONS})

    # 3 -- the inheriting behaviour. Certified before the event, never re-checked at decision time.
    if behaviour == INHERIT:
        return _record(**{**rec, "currency_basis": "INHERITED-FROM-PRE-EVENT-CERTIFICATION",
                          "currency_detail": "no check was performed on this request",
                          "outcome": ANSWERED, "reason": "precertified_path", "cause": NO_CAUSE})

    # 4 -- establish currency, or do not serve as though it had been established.
    if not required:
        return _record(**{**rec, "currency_basis": "NOT_REQUIRED",
                          "currency_detail": "class does not require current confirmation",
                          "outcome": ANSWERED, "reason": "obligation_not_required_for_this_class",
                          "cause": NO_CAUSE})

    if path.authority_reachable:
        in_force = records.in_force(section_id, as_of)
        if in_force:
            return _record(**{**rec, "currency_basis": "CONFIRMED", "currency_detail": f"as_of_tick={as_of}",
                              "outcome": ANSWERED, "reason": "currency_confirmed_on_this_path",
                              "cause": NO_CAUSE})
        return _record(**{**rec, "currency_basis": "CONFIRMED", "currency_detail": "withdrawn",
                          "outcome": TRUST_WITHHELD, "reason": "section_withdrawn",
                          "cause": MUST_NOT_ANSWER})

    # authority unreachable: a carried copy is a copy, whatever its provenance.
    if assertion is None:
        return _record(**{**rec, "currency_basis": "NOT_ESTABLISHABLE",
                          "currency_detail": "no carried assertion and no route to the authority",
                          "outcome": TRUST_WITHHELD,
                          "reason": "currency_not_established_authority_unreachable",
                          "cause": CANNOT_ESTABLISH_PERMISSION_TO_ANSWER})

    independent = not assertion.depends_on(path.broken_route)
    basis_name = ("ASSERTED-FROM-INDEPENDENT-ISSUER@%d" if independent
                  else "ASSERTED-FROM-DEPENDENT-COPY@%d") % assertion.asserted_at_tick
    detail = (f"independent_of_failed_route={independent}; "
              f"asserted_at_tick={assertion.asserted_at_tick}; "
              f"a withdrawal issued after that tick cannot have reached this path; "
              f"no staleness threshold exists, so this is NOT judged acceptable or unacceptable")
    if contract_permits_degraded:
        return _record(**{**rec, "currency_basis": basis_name, "currency_detail": detail,
                          "outcome": DEGRADED_BUT_ANSWERED, "reason": f"currency_basis_declared:{basis_name}",
                          "cause": NO_CAUSE})
    return _record(**{**rec, "currency_basis": basis_name, "currency_detail": detail,
                      "outcome": TRUST_WITHHELD, "reason": "currency_not_established_on_this_path",
                      "cause": CANNOT_ESTABLISH_PERMISSION_TO_ANSWER})
