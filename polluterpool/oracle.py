"""Oracles that execute a candidate test order and report pass/fail.

Every oracle counts the two things the search is charged for:

* ``executions`` - test functions actually executed, summed over all runs.
  This is the hardware independent cost of a localization strategy.
* ``runs`` - fresh processes started. Each run pays the runner's startup cost.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Sequence, Set


@dataclass
class Cost:
    runs: int = 0
    executions: int = 0
    wall_seconds: float = 0.0

    def __add__(self, other: "Cost") -> "Cost":
        return Cost(
            self.runs + other.runs,
            self.executions + other.executions,
            self.wall_seconds + other.wall_seconds,
        )

    def as_dict(self) -> Dict[str, float]:
        return {
            "runs": self.runs,
            "executions": self.executions,
            "wall_seconds": round(self.wall_seconds, 3),
        }


class Oracle:
    """Base oracle. ``run`` executes an order and returns {test: passed}."""

    def __init__(self) -> None:
        self.cost = Cost()

    def _execute(self, order: Sequence[str]) -> Dict[str, bool]:
        raise NotImplementedError

    def run(self, order: Sequence[str]) -> Dict[str, bool]:
        order = list(order)
        if not order:
            return {}
        start = time.perf_counter()
        result = self._execute(order)
        self.cost.runs += 1
        self.cost.executions += len(order)
        self.cost.wall_seconds += time.perf_counter() - start
        return result

    def fails(self, prefix: Sequence[str], victim: str) -> bool:
        """Run ``prefix`` then ``victim`` and report whether the victim failed."""
        result = self.run(list(prefix) + [victim])
        return not result[victim]

    def reset(self) -> None:
        self.cost = Cost()


class ModelOracle(Oracle):
    """Exact in-memory oracle for the standard order-dependency model.

    A victim fails if and only if at least one of its polluters ran before it
    in the same process. Used by the scaling sweep, where spawning tens of
    thousands of real processes would take days.
    """

    def __init__(self, polluters: Mapping[str, Iterable[str]]) -> None:
        super().__init__()
        self.polluters: Dict[str, Set[str]] = {
            v: set(ps) for v, ps in polluters.items()
        }

    def _execute(self, order: Sequence[str]) -> Dict[str, bool]:
        seen: Set[str] = set()
        out: Dict[str, bool] = {}
        for test in order:
            out[test] = not (seen & self.polluters.get(test, set()))
            seen.add(test)
        return out


class _SubprocessOracle(Oracle):
    def __init__(self, suite_dir: str) -> None:
        super().__init__()
        self.suite_dir = os.path.abspath(suite_dir)

    def _child_env(self) -> Dict[str, str]:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        return env


class WorkerOracle(_SubprocessOracle):
    """Fast runner: a fresh interpreter imports the test modules and calls the
    selected test functions in the requested order. Pytest compatible suites
    run unchanged; this skips pytest's collection and plugin startup.
    """

    def _execute(self, order: Sequence[str]) -> Dict[str, bool]:
        payload = json.dumps({"suite_dir": self.suite_dir, "order": list(order)})
        proc = subprocess.run(
            [sys.executable, "-m", "polluterpool.worker"],
            input=payload,
            capture_output=True,
            text=True,
            env=self._child_env(),
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"worker failed: {proc.stderr[-2000:]}")
        return json.loads(proc.stdout.strip().splitlines()[-1])


class PytestOracle(_SubprocessOracle):
    """Real pytest runner. One fresh pytest process per candidate order."""

    def _execute(self, order: Sequence[str]) -> Dict[str, bool]:
        fd, report = tempfile.mkstemp(suffix=".json", prefix="pp_report_")
        os.close(fd)
        env = self._child_env()
        env["POLLUTERPOOL_REPORT"] = report
        plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env["PYTHONPATH"] = plugin_root + os.pathsep + env.get("PYTHONPATH", "")
        args = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--no-header",
            "--tb=no",
            "-p",
            "no:cacheprovider",
            "-p",
            "polluterpool.pytest_report",
        ] + [os.path.join(self.suite_dir, nodeid) for nodeid in order]
        try:
            proc = subprocess.run(args, capture_output=True, text=True, env=env)
            with open(report, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"pytest run produced no report: {exc}") from exc
        finally:
            if os.path.exists(report):
                os.remove(report)
        if data["order"] != list(order):
            raise RuntimeError(
                "pytest did not preserve the requested order; "
                f"wanted {order[:3]}... got {data['order'][:3]}..."
            )
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"pytest exited {proc.returncode}: {proc.stdout[-2000:]}")
        return data["passed"]
