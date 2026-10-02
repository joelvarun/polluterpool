"""Fresh-process test runner used by :class:`WorkerOracle`.

Reads ``{"suite_dir": ..., "order": [...]}`` on stdin, imports the referenced
modules, calls the test functions in the given order inside one process, and
writes ``{nodeid: passed}`` as JSON on stdout. State left behind by one test is
visible to the next, which is the whole point.
"""

from __future__ import annotations

import importlib
import json
import sys
from typing import Dict


def main() -> int:
    request = json.loads(sys.stdin.read())
    suite_dir = request["suite_dir"]
    order = request["order"]
    if suite_dir not in sys.path:
        sys.path.insert(0, suite_dir)

    results: Dict[str, bool] = {}
    for nodeid in order:
        filename, _, funcname = nodeid.partition("::")
        modname = filename[:-3] if filename.endswith(".py") else filename
        try:
            module = importlib.import_module(modname)
            getattr(module, funcname)()
        except Exception:  # a failing test is data, not an error
            results[nodeid] = False
        else:
            results[nodeid] = True
    sys.stdout.write(json.dumps(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
