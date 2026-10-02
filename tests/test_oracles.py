"""The two runners must agree, and must charge the same cost."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polluterpool import PytestOracle, Suite, WorkerOracle  # noqa: E402

SUITE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "demo_suite"
)


def test_runners_agree_on_the_full_suite_order():
    with open(os.path.join(SUITE_DIR, "manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    order = manifest["order"]
    worker = WorkerOracle(SUITE_DIR).run(order)
    pytest_result = PytestOracle(SUITE_DIR).run(order)
    assert worker == pytest_result
    assert sorted(t for t, ok in worker.items() if not ok) == sorted(manifest["victims"])


def test_cost_counts_every_execution_and_every_run():
    from polluterpool import ModelOracle

    suite = Suite(["a", "b", "c", "d"])
    oracle = ModelOracle({"d": {"b"}})
    assert oracle.run(suite.tests)["d"] is False
    assert oracle.fails(["b"], "d") is True
    assert oracle.fails(["a", "c"], "d") is False
    assert oracle.cost.runs == 3
    assert oracle.cost.executions == 4 + 2 + 3
