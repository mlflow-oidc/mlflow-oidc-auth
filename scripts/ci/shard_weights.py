"""Rebuild ``mlflow_oidc_auth/tests/shard_weights.json`` from JUnit XML reports.

The weights only balance the CI shards; they never decide whether a test runs. Refresh them when
one shard is noticeably slower than the others — download the ``unit-test-shard-*`` artifacts of
a recent "Unit tests" run and pass their ``junit.xml`` files:

    python scripts/ci/shard_weights.py shard-*/junit.xml

Each file's weight is the sum of its test case times (setup + call + teardown, as pytest reports
them), rounded to 0.1 s.
"""

import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

TESTS_PACKAGE = "mlflow_oidc_auth.tests."
OUTPUT = Path(__file__).resolve().parents[2] / "mlflow_oidc_auth" / "tests" / "shard_weights.json"


def weights_from_junit(paths: List[str]) -> Dict[str, float]:
    """Sum test case durations per test file.

    Parameters:
        paths: JUnit XML report paths written by ``pytest --junitxml``.

    Returns:
        Test file path relative to ``mlflow_oidc_auth/tests`` mapped to its total seconds.
    """
    totals: Dict[str, float] = defaultdict(float)
    for path in paths:
        for case in ET.parse(path).getroot().iter("testcase"):
            classname = case.get("classname", "")
            if not classname.startswith(TESTS_PACKAGE):
                continue
            # classname is "pkg.module" or "pkg.module.Class[.Nested]"; the module is the first
            # dotted prefix that names an existing file.
            parts = classname[len(TESTS_PACKAGE) :].split(".")
            for end in range(len(parts), 0, -1):
                candidate = "/".join(parts[:end]) + ".py"
                if (OUTPUT.parent / candidate).exists():
                    totals[candidate] += float(case.get("time", 0) or 0)
                    break
    return {path: round(seconds, 1) for path, seconds in sorted(totals.items())}


if __name__ == "__main__":
    weights = weights_from_junit(sys.argv[1:])
    OUTPUT.write_text(json.dumps(weights, indent=1, sort_keys=True) + "\n")
    print(f"wrote {len(weights)} file weights ({sum(weights.values()):.0f}s total) to {OUTPUT}")
