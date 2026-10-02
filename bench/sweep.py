"""Scaling sweep on the exact order-dependency model.

The real suite pins the numbers to real processes; this sweep answers the
question the real suite cannot afford to: how the three strategies separate as
the suite and the number of victims grow. The oracle here is the exact model
every strategy already assumes, so the execution counts are the same quantity
measured on the real suite, just without paying process startup for each of
the hundreds of thousands of test executions involved.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polluterpool import (  # noqa: E402
    ModelOracle,
    Suite,
    localize_bisect,
    localize_ddmin,
    localize_pool,
)

STRATEGIES = [
    ("ddmin", localize_ddmin),
    ("bisect", localize_bisect),
    ("pool", localize_pool),
]


def make_case(seed: int, n_tests: int, n_victims: int, max_polluters: int):
    rng = random.Random(seed)
    suite = Suite(f"t{i:05d}" for i in range(n_tests))
    victims = sorted(
        rng.sample(suite.tests[n_tests // 4 :], n_victims), key=suite.pos.__getitem__
    )
    truth = {}
    for victim in victims:
        pool = suite.before(victim)
        count = rng.randint(1, max_polluters)
        truth[victim] = set(rng.sample(pool, min(count, len(pool))))
    return suite, victims, truth


def measure(n_tests: int, n_victims: int, max_polluters: int, repeats: int):
    totals = {key: {"executions": 0, "runs": 0} for key, _ in STRATEGIES}
    for seed in range(repeats):
        suite, victims, truth = make_case(seed, n_tests, n_victims, max_polluters)
        for key, localize in STRATEGIES:
            oracle = ModelOracle(truth)
            if localize(oracle, suite, victims) != truth:
                raise SystemExit(f"{key} wrong on seed {seed}")
            totals[key]["executions"] += oracle.cost.executions
            totals[key]["runs"] += oracle.cost.runs
    return {
        key: {name: value / repeats for name, value in counts.items()}
        for key, counts in totals.items()
    }


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--max-polluters", type=int, default=3)
    parser.add_argument("--out", default=os.path.join(root, "docs", "results_sweep.json"))
    args = parser.parse_args()

    by_size = []
    for n_tests in (100, 200, 400, 800, 1600):
        row = measure(n_tests, 8, args.max_polluters, args.repeats)
        by_size.append({"n_tests": n_tests, **row})
        print(f"n_tests={n_tests:<5} " + "  ".join(
            f"{k}={row[k]['executions']:.0f}" for k, _ in STRATEGIES), flush=True)

    by_victims = []
    for n_victims in (1, 2, 4, 8, 16, 32):
        row = measure(800, n_victims, args.max_polluters, args.repeats)
        by_victims.append({"n_victims": n_victims, **row})
        print(f"victims={n_victims:<4} " + "  ".join(
            f"{k}={row[k]['executions']:.0f}" for k, _ in STRATEGIES), flush=True)

    payload = {
        "repeats": args.repeats,
        "max_polluters": args.max_polluters,
        "by_size": by_size,
        "by_victims": by_victims,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
