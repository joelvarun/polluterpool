"""Ordered test suite model."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple


class Suite:
    """An ordered list of test ids.

    The suite order is the order the test runner would use by default. Every
    candidate order produced by the search is a subsequence of it, so a test
    never moves relative to another test.
    """

    def __init__(self, tests: Iterable[str]) -> None:
        self.tests: Tuple[str, ...] = tuple(tests)
        if len(set(self.tests)) != len(self.tests):
            raise ValueError("duplicate test ids in suite")
        self.pos: Dict[str, int] = {t: i for i, t in enumerate(self.tests)}

    def __len__(self) -> int:
        return len(self.tests)

    def __iter__(self):
        return iter(self.tests)

    def __contains__(self, item: object) -> bool:
        return item in self.pos

    def order(self, subset: Iterable[str]) -> List[str]:
        """Return subset sorted into suite order."""
        return sorted(set(subset), key=self.pos.__getitem__)

    def before(self, test: str) -> List[str]:
        """Every test that precedes ``test`` in suite order."""
        return list(self.tests[: self.pos[test]])
