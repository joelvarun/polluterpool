"""Per-victim localization baselines.

Both baselines treat one victim at a time, which is what the existing tools do:
each candidate order ends with a single victim, so one run answers one question
about one victim.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set

from .oracle import Oracle
from .suite import Suite


def _candidates(suite: Suite, victim: str) -> List[str]:
    return suite.before(victim)


def localize_bisect(
    oracle: Oracle, suite: Suite, victims: Sequence[str]
) -> Dict[str, Set[str]]:
    """Generalized binary splitting, one victim at a time.

    The whole prefix of a victim is known to contain at least one polluter
    (that is what made it a victim), so the search starts from one positive
    segment and splits it until every candidate is proven clean or proven to be
    a polluter.
    """
    result: Dict[str, Set[str]] = {}
    for victim in victims:
        found: Set[str] = set()
        clean: Set[str] = set()
        queue: List[List[str]] = [_candidates(suite, victim)]
        while queue:
            segment = [t for t in queue.pop(0) if t not in clean and t not in found]
            if not segment:
                continue
            if len(segment) == 1:
                found.add(segment[0])
                continue
            mid = len(segment) // 2
            left, right = segment[:mid], segment[mid:]
            if oracle.fails(left, victim):
                queue.append(left)
                if oracle.fails(right, victim):
                    queue.append(right)
                else:
                    clean.update(right)
            else:
                clean.update(left)
                queue.append(right)
        result[victim] = found
    return result


def _ddmin(oracle: Oracle, victim: str, candidates: List[str]) -> List[str]:
    """Classic delta debugging: shrink a failing input to a 1-minimal one."""
    current = list(candidates)
    granularity = 2
    while len(current) >= 2:
        chunk = max(1, len(current) // granularity)
        chunks = [current[i : i + chunk] for i in range(0, len(current), chunk)]
        for part in chunks:
            if oracle.fails(part, victim):
                current, granularity = part, 2
                break
        else:
            for part in chunks:
                complement = [t for t in current if t not in set(part)]
                if complement and oracle.fails(complement, victim):
                    current = complement
                    granularity = max(granularity - 1, 2)
                    break
            else:
                if granularity >= len(current):
                    break
                granularity = min(2 * granularity, len(current))
    return current


def localize_ddmin(
    oracle: Oracle, suite: Suite, victims: Sequence[str]
) -> Dict[str, Set[str]]:
    """Iterated delta debugging, the reducer the flaky-test literature uses."""
    result: Dict[str, Set[str]] = {}
    for victim in victims:
        found: Set[str] = set()
        remaining = _candidates(suite, victim)
        while remaining and oracle.fails(remaining, victim):
            minimal = _ddmin(oracle, victim, remaining)
            found.update(minimal)
            blocked = set(minimal)
            remaining = [t for t in remaining if t not in blocked]
        result[victim] = found
    return result
