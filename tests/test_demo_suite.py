"""End to end check on the generated pytest suite, using the fast runner."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polluterpool import (  # noqa: E402
    Suite,
    WorkerOracle,
    discover_victims,
    localize_pool,
)

SUITE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "demo_suite"
)


@pytest.fixture(scope="module")
def manifest():
    with open(os.path.join(SUITE_DIR, "manifest.json"), encoding="utf-8") as handle:
        return json.load(handle)


def test_suite_order_reproduces_the_planted_victims(manifest):
    suite = Suite(manifest["order"])
    oracle = WorkerOracle(SUITE_DIR)
    victims = discover_victims(oracle, suite)
    assert sorted(victims, key=suite.pos.__getitem__) == manifest["victims"]


def test_pool_recovers_the_planted_polluters(manifest):
    suite = Suite(manifest["order"])
    oracle = WorkerOracle(SUITE_DIR)
    found = localize_pool(oracle, suite, manifest["victims"])
    expected = {v: set(ps) for v, ps in manifest["ground_truth"].items()}
    assert found == expected
