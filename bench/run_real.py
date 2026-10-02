"""Localize every planted polluter in the real pytest suite, three ways.

Each strategy gets a fresh oracle, so the reported cost is only what that
strategy spent. Victim discovery is identical for all three and is reported on
its own line.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polluterpool import (  # noqa: E402
    PytestOracle,
    Suite,
    WorkerOracle,
    discover_victims,
    localize_bisect,
    localize_ddmin,
    localize_pool,
)

STRATEGIES = [
    ("ddmin", "Delta debugging (ddmin)", localize_ddmin),
    ("bisect", "Binary splitting", localize_bisect),
    ("pool", "polluterpool", localize_pool),
]


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default=os.path.join(root, "examples", "demo_suite"))
    parser.add_argument("--runner", choices=("pytest", "worker"), default="pytest")
    parser.add_argument("--out", default=os.path.join(root, "docs", "results_real.json"))
    args = parser.parse_args()

    with open(os.path.join(args.suite, "manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    suite = Suite(manifest["order"])
    truth = {v: set(ps) for v, ps in manifest["ground_truth"].items()}
    make_oracle = PytestOracle if args.runner == "pytest" else WorkerOracle

    oracle = make_oracle(args.suite)
    started = time.time()
    victims = discover_victims(oracle, suite)
    discovery = oracle.cost.as_dict()
    if sorted(victims, key=suite.pos.__getitem__) != manifest["victims"]:
        raise SystemExit(f"discovery mismatch: {victims} != {manifest['victims']}")
    print(
        f"discovery: {len(victims)} victims, {discovery['executions']} executions, "
        f"{discovery['runs']} runs, {discovery['wall_seconds']:.1f}s",
        flush=True,
    )

    results = {}
    for key, label, localize in STRATEGIES:
        oracle = make_oracle(args.suite)
        found = localize(oracle, suite, victims)
        if found != truth:
            raise SystemExit(f"{key} returned the wrong polluters")
        results[key] = {"label": label, **oracle.cost.as_dict()}
        print(
            f"{label:<24} {oracle.cost.executions:>7} executions  "
            f"{oracle.cost.runs:>5} runs  {oracle.cost.wall_seconds:7.1f}s",
            flush=True,
        )

    payload = {
        "runner": args.runner,
        "suite_tests": len(suite),
        "victims": len(victims),
        "pairs": sum(len(p) for p in truth.values()),
        "discovery": discovery,
        "strategies": results,
        "total_wall_seconds": round(time.time() - started, 1),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
