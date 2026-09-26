"""Serving paths. The whole point: reaching the PATH and reaching the AUTHORITY are different things.

Keep them as two separate switches and the exercises work. Collapse them into one "healthy" flag and
the episode's subject disappears -- which is exactly the mistake the lab is about.
"""
from dataclasses import dataclass, field


@dataclass
class ValidityAssertion:
    """A carried claim that a section was in force. It is a COPY, and copies have provenance."""
    section_id: str
    asserted_in_force: bool
    asserted_at_tick: int
    provenance: list                 # ordered inputs this assertion rests on
    refresh_route: str | None        # the route needed to renew it; None means it needs no route

    def depends_on(self, broken_route):
        return broken_route in self.provenance or self.refresh_route == broken_route


@dataclass
class Path:
    name: str
    path_reachable: bool = True          # can a caller reach this path at all?
    authority_reachable: bool = True     # can THIS path reach the records system?
    broken_route: str = "cross-boundary-authority-route"
    carried: dict = field(default_factory=dict)      # section_id -> ValidityAssertion

    def health(self):
        """What an ordinary availability dashboard would show. Deliberately incomplete."""
        return {
            "service_reachable": self.path_reachable,
            "path_health": "green" if self.path_reachable else "red",
            "answer_produced": self.path_reachable,
        }


def primary():
    return Path("primary", True, True)


def failover_with_replica(asserted_at_tick=0):
    """The second region: it serves, and it carries copies whose renewal needs the failed route."""
    p = Path("failover", path_reachable=True, authority_reachable=False)
    for section_id in ("D-204-S1", "D-204-S3", "D-204-S4", "D-900-S1"):
        p.carried[section_id] = ValidityAssertion(
            section_id, True, asserted_at_tick,
            provenance=["replica-snapshot", "cross-boundary-authority-route", "records-system"],
            refresh_route="cross-boundary-authority-route")
    return p


def failover_with_issuer_window(asserted_at_tick=0):
    """Option E in miniature: the assertion is anchored at the issuer, so it needs no route to renew.

    Independent -- and still only as current as the moment it was issued. That distinction is step 5.
    """
    p = Path("failover", path_reachable=True, authority_reachable=False)
    for section_id in ("D-204-S1", "D-204-S3", "D-204-S4", "D-900-S1"):
        p.carried[section_id] = ValidityAssertion(
            section_id, True, asserted_at_tick,
            provenance=["issuer-embedded-validity-window"], refresh_route=None)
    return p
