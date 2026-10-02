"""Command line entry point: find the polluters in a pytest suite directory.

    python -m polluterpool path/to/tests

The directory is expected to be flat (test modules directly inside it), which
is what keeps a bare ``file.py::function`` node id unambiguous for both
runners.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import List

from .baselines import localize_bisect, localize_ddmin
from .discover import discover_victims
from .oracle import PytestOracle, WorkerOracle
from .pool import localize_pool
from .suite import Suite

STRATEGIES = {
    "pool": localize_pool,
    "bisect": localize_bisect,
    "ddmin": localize_ddmin,
}


def collect_order(suite_dir: str) -> List[str]:
    """Ask pytest for the suite's default execution order."""
    env = dict(os.environ)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            suite_dir,
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    order = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("<"):
            order.append(line.replace("\\", "/").rsplit("/", 1)[-1])
    if not order:
        raise SystemExit(f"pytest collected nothing in {suite_dir}:\n{proc.stdout}")
    return order


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", help="directory holding the test modules")
    parser.add_argument("--runner", choices=("pytest", "worker"), default="pytest")
    parser.add_argument("--strategy", choices=sorted(STRATEGIES), default="pool")
    parser.add_argument("--json", dest="json_out", default=None)
    args = parser.parse_args(argv)

    suite = Suite(collect_order(args.suite))
    oracle = (PytestOracle if args.runner == "pytest" else WorkerOracle)(args.suite)

    victims = discover_victims(oracle, suite)
    print(f"{len(suite)} tests collected, {len(victims)} order dependent victims")
    if not victims:
        print("no test passes alone and fails in suite order; nothing to localize")
        return 0
    discovery = oracle.cost.as_dict()

    oracle.reset()
    found = STRATEGIES[args.strategy](oracle, suite, victims)
    for victim in victims:
        for polluter in suite.order(found[victim]):
            print(f"  {polluter}  pollutes  {victim}")
    print(
        f"discovery: {discovery['executions']} executions in {discovery['runs']} runs; "
        f"localization ({args.strategy}): {oracle.cost.executions} executions in "
        f"{oracle.cost.runs} runs, {oracle.cost.wall_seconds:.1f}s"
    )
    if args.json_out:
        payload = {
            "victims": {v: suite.order(found[v]) for v in victims},
            "discovery": discovery,
            "localization": {"strategy": args.strategy, **oracle.cost.as_dict()},
        }
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
