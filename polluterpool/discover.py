"""Find the victims: tests that pass alone but fail in suite order."""

from __future__ import annotations

from typing import List

from .oracle import Oracle
from .suite import Suite


def discover_victims(oracle: Oracle, suite: Suite) -> List[str]:
    """One full-suite run plus one isolation run per failing test.

    Both localization strategies start from this same victim list, so the
    discovery cost is identical for all of them and is reported separately.
    """
    outcome = oracle.run(list(suite.tests))
    failing = [t for t in suite.tests if not outcome[t]]
    victims = [t for t in failing if oracle.run([t])[t]]
    return victims
