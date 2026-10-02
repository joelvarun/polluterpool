"""Shared-tail group testing for order-dependent test localization.

The observation this is built on: a candidate order is a prefix plus a tail.
The expensive part is the prefix. Appending every unresolved victim to the same
prefix turns one run into one observation per victim, at the cost of one extra
test execution each, instead of one observation per run.

Three things make the shared prefix usable:

* The prefix is grown from the probe of the least recently served victim, and
  another victim's probe joins only if the combined prefix still cuts that
  victim's own search region exactly where it asked. At least one victim's
  binary search therefore advances every round, which is what makes the search
  terminate. Victims are considered cheapest probe first, so a small prefix
  leaves room for others to join it.
* Victims that cannot be served exactly still ride along for one extra
  execution each. Inference is done against the tests that actually ran before
  the victim, not against the split that was requested, so a pooled run is
  always sound even when it is not the split that victim wanted.
* Known polluters are kept out of the prefix of the victims they belong to.
  Without that, a victim's result is forced to fail and the run teaches it
  nothing.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .baselines import localize_bisect
from .oracle import Oracle
from .suite import Suite

_ROUND_LIMIT = 8


class _State:
    """Per victim knowledge: what is clean, what is guilty, what is still open.

    ``constraints`` holds sets known to contain at least one polluter that has
    not been named yet. A constraint that shrinks to one element names a
    polluter; constraints a named polluter satisfies are dropped.
    """

    def __init__(self, suite: Suite, victims: Sequence[str]) -> None:
        self.suite = suite
        self.victims = list(victims)
        self.cand: Dict[str, Set[str]] = {}
        self.clean: Dict[str, Set[str]] = {}
        self.found: Dict[str, Set[str]] = {}
        self.constraints: Dict[str, List[Set[str]]] = {}
        self.served: Dict[str, int] = {v: -1 for v in victims}
        for victim in victims:
            prefix = set(suite.before(victim))
            self.cand[victim] = set(prefix)
            self.clean[victim] = set()
            self.found[victim] = set()
            self.constraints[victim] = [set(prefix)] if prefix else []

    def resolved(self, victim: str) -> bool:
        return not self.cand[victim]

    def mark_clean(self, victim: str, cleaned: Iterable[str]) -> None:
        cleaned = set(cleaned) & self.cand[victim]
        if not cleaned:
            return
        self.clean[victim] |= cleaned
        self.cand[victim] -= cleaned
        for group in self.constraints[victim]:
            group -= cleaned

    def add_constraint(self, victim: str, group: Iterable[str]) -> None:
        group = set(group) & self.cand[victim]
        if not group:
            return
        existing = self.constraints[victim]
        if any(known <= group for known in existing):
            return
        self.constraints[victim] = [k for k in existing if not group <= k] + [group]

    def settle(self, victim: str) -> None:
        """Promote every singleton constraint to a confirmed polluter."""
        changed = True
        while changed:
            changed = False
            for group in list(self.constraints[victim]):
                if not group:
                    raise AssertionError("empty constraint: order model violated")
                if len(group) == 1:
                    polluter = next(iter(group))
                    self.found[victim].add(polluter)
                    self.cand[victim].discard(polluter)
                    self.constraints[victim] = [
                        g for g in self.constraints[victim] if polluter not in g
                    ]
                    changed = True
                    break

    def probe(self, victim: str) -> Set[str]:
        """The prefix this victim wants to run next.

        While an unsatisfied constraint exists, half of the smallest one is
        what turns it into a named polluter. Once every constraint is
        satisfied, the whole remaining candidate set is swept in one shot: if
        it passes, the victim is fully explained and done.
        """
        groups = self.constraints[victim]
        if not groups:
            return set(self.cand[victim])
        group = min(groups, key=len)
        ordered = self.suite.order(group)
        return set(ordered[: max(1, len(ordered) // 2)])


def _exact_for(state: _State, victim: str, universe: Set[str], probe: Set[str]) -> bool:
    """True when ``universe`` runs exactly the probe this victim asked for."""
    if universe & state.found[victim]:
        return False
    return (universe & state.cand[victim]) == probe


def _plan_round(
    state: _State, unresolved: Sequence[str]
) -> Tuple[Set[str], List[str]]:
    """Choose one pooled prefix and the victims that will read it."""
    probes = {v: state.probe(v) for v in unresolved}
    probes = {v: p for v, p in probes.items() if p}
    ranked = sorted(
        probes,
        key=lambda v: (state.served[v], len(probes[v]), state.suite.pos[v]),
    )

    pool: Set[str] = set()
    served_exactly: List[str] = []
    for victim in ranked:
        trial_pool = pool | probes[victim]
        trial_served = served_exactly + [victim]
        universe = trial_pool | set(trial_served)
        if all(_exact_for(state, w, universe, probes[w]) for w in trial_served):
            pool, served_exactly = trial_pool, trial_served

    riders: List[str] = []
    rest = [v for v in ranked if v not in served_exactly]
    for victim in served_exactly + rest:
        universe = pool | set(riders) | {victim}
        if universe & state.found[victim]:
            continue  # a polluter we already named would mask the answer
        if any(victim in state.found[w] for w in riders):
            continue  # running this victim would pollute one already in the tail
        if not (universe & state.cand[victim]):
            continue  # it would learn nothing it does not already know
        if any(
            not _exact_for(state, w, universe, probes[w])
            for w in riders
            if w in served_exactly
        ):
            continue  # it would spoil a split somebody is relying on
        riders.append(victim)
    return pool, riders


def _screen_victims(oracle: Oracle, suite: Suite, state: _State) -> None:
    """Decide every victim-pollutes-victim pair before pooling starts.

    A shared tail is only sound if no victim in it pollutes a later one. There
    are few victims, so settling those pairs up front is cheap, and it feeds
    real polluters into the main search.
    """
    for victim in state.victims:
        earlier = [v for v in state.victims if suite.pos[v] < suite.pos[victim]]
        if not earlier:
            continue
        if not oracle.fails(earlier, victim):
            state.mark_clean(victim, earlier)
            state.settle(victim)
            continue
        sub = Suite(suite.order(set(earlier) | {victim}))
        guilty = localize_bisect(oracle, sub, [victim])[victim]
        for polluter in guilty:
            state.found[victim].add(polluter)
            state.cand[victim].discard(polluter)
            state.constraints[victim] = [
                g for g in state.constraints[victim] if polluter not in g
            ]
        state.mark_clean(victim, set(earlier) - guilty)
        state.settle(victim)


def localize_pool(
    oracle: Oracle, suite: Suite, victims: Sequence[str]
) -> Dict[str, Set[str]]:
    """Localize every polluter of every victim with shared-prefix runs."""
    state = _State(suite, victims)
    _screen_victims(oracle, suite, state)

    limit = _ROUND_LIMIT * (1 + len(victims)) * max(1, len(suite).bit_length())
    for round_index in range(limit):
        unresolved = [v for v in state.victims if not state.resolved(v)]
        if not unresolved:
            return {v: set(state.found[v]) for v in state.victims}
        pool, riders = _plan_round(state, unresolved)
        if not riders:
            raise AssertionError("no informative probe available")
        universe = pool | set(riders)
        outcome = oracle.run(suite.order(universe))
        for victim in riders:
            if universe & state.found[victim]:
                raise AssertionError("a known polluter reached a rider's prefix")
            observed = universe & state.cand[victim]
            if not observed:
                continue
            if outcome[victim]:
                state.mark_clean(victim, observed)
            else:
                state.add_constraint(victim, observed)
            state.settle(victim)
            state.served[victim] = round_index
    raise AssertionError("pooled search did not converge")
