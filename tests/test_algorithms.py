"""Randomized equivalence tests against the exact order-dependency model."""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polluterpool import (  # noqa: E402
    ModelOracle,
    Suite,
    discover_victims,
    localize_bisect,
    localize_ddmin,
    localize_pool,
)


def make_case(seed: int, n_tests: int = 60, n_victims: int = 5, max_polluters: int = 3):
    rng = random.Random(seed)
    tests = [f"t{i:04d}" for i in range(n_tests)]
    suite = Suite(tests)
    victims = sorted(
        rng.sample(tests[n_tests // 5 :], n_victims), key=suite.pos.__getitem__
    )
    truth = {}
    for victim in victims:
        pool = suite.before(victim)
        count = rng.randint(1, min(max_polluters, len(pool)))
        truth[victim] = set(rng.sample(pool, count))
    return suite, victims, truth


def test_all_strategies_recover_ground_truth():
    for seed in range(25):
        suite, victims, truth = make_case(seed)
        oracle = ModelOracle(truth)
        found_victims = discover_victims(oracle, suite)
        assert found_victims == victims, seed
        for localize in (localize_bisect, localize_ddmin, localize_pool):
            oracle = ModelOracle(truth)
            got = localize(oracle, suite, victims)
            assert got == truth, (localize.__name__, seed, got, truth)


def test_pool_handles_victims_that_pollute_victims():
    rng = random.Random(7)
    tests = [f"t{i:04d}" for i in range(40)]
    suite = Suite(tests)
    victims = [tests[10], tests[20], tests[30]]
    truth = {
        tests[10]: {tests[2]},
        tests[20]: {tests[10]},
        tests[30]: {tests[10], tests[20], tests[5]},
    }
    for localize in (localize_bisect, localize_ddmin, localize_pool):
        oracle = ModelOracle(truth)
        assert localize(oracle, suite, victims) == truth, localize.__name__
    assert rng.random() >= 0.0


def test_single_victim_single_polluter():
    tests = [f"t{i:04d}" for i in range(16)]
    suite = Suite(tests)
    truth = {tests[9]: {tests[3]}}
    oracle = ModelOracle(truth)
    assert localize_pool(oracle, suite, [tests[9]]) == truth


if __name__ == "__main__":
    test_all_strategies_recover_ground_truth()
    test_pool_handles_victims_that_pollute_victims()
    test_single_victim_single_polluter()
    print("all algorithm tests passed")
