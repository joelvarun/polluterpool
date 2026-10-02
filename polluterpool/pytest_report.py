"""Pytest plugin that records execution order and per-test outcome as JSON.

Enabled with ``-p polluterpool.pytest_report``; the destination file comes from
the ``POLLUTERPOOL_REPORT`` environment variable.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

_ORDER: List[str] = []
_PASSED: Dict[str, bool] = {}


def _short(nodeid: str) -> str:
    return nodeid.replace("\\", "/").rsplit("/", 1)[-1]


def pytest_runtest_logreport(report) -> None:
    nodeid = _short(report.nodeid)
    if report.when == "setup":
        _ORDER.append(nodeid)
        _PASSED[nodeid] = True
    if not report.passed:
        _PASSED[nodeid] = False


def pytest_sessionfinish(session, exitstatus) -> None:
    path = os.environ.get("POLLUTERPOOL_REPORT")
    if not path:
        return
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"order": _ORDER, "passed": _PASSED}, handle)
