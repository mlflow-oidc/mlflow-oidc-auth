"""Verify that the unit-test shards ran the whole suite, each test file exactly once.

Reads the ``--shard-report`` JSON written by every shard (see ``mlflow_oidc_auth/tests/_sharding.py``)
and exits non-zero unless:

- there is exactly one report per shard index ``0..N-1``, all with the same shard count;
- every shard collected the same suite (same item count, same file list hash);
- the selected files are disjoint and their union is the full collected file list;
- the selected test counts add up to the full collected test count.

Usage: ``python scripts/ci/check_shards.py REPORT.json [REPORT.json ...]``
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import List


def check(reports: List[dict]) -> List[str]:
    """Return a list of problems with the shard reports; empty when they partition the suite.

    Parameters:
        reports: The parsed shard reports.

    Returns:
        Human-readable error messages.
    """
    if not reports:
        return ["no shard reports found"]
    errors = []
    counts = {r["shard_count"] for r in reports}
    if len(counts) != 1:
        return [f"shards disagree on the shard count: {sorted(counts)}"]
    shard_count = counts.pop()
    indices = sorted(r["shard_index"] for r in reports)
    if indices != list(range(shard_count)):
        errors.append(f"expected one report per shard 0..{shard_count - 1}, got indices {indices}")
    for key in ("collected_items", "collected_files", "collected_files_sha256"):
        values = {r[key] for r in reports}
        if len(values) != 1:
            errors.append(f"shards collected different suites ({key}: {sorted(map(str, values))})")
    seen = {}
    for r in reports:
        for path in r["selected_files"]:
            if path in seen:
                errors.append(f"{path} ran in shard {seen[path]} and shard {r['shard_index']}")
            seen[path] = r["shard_index"]
    union = sorted(seen)
    first = reports[0]
    if len(union) != first["collected_files"] or hashlib.sha256("\n".join(union).encode()).hexdigest() != first["collected_files_sha256"]:
        errors.append(f"shards ran {len(union)} files, but {first['collected_files']} were collected")
    selected = sum(r["selected_items"] for r in reports)
    if selected != first["collected_items"]:
        errors.append(f"shards selected {selected} tests, but {first['collected_items']} were collected")
    return errors


def main(argv: List[str]) -> int:
    """Check the reports named on the command line and print a summary.

    Parameters:
        argv: Report file paths.

    Returns:
        Process exit code: 0 when the shards partition the suite, 1 otherwise.
    """
    reports = [json.loads(Path(p).read_text()) for p in argv]
    for r in sorted(reports, key=lambda r: r["shard_index"]):
        print(f"shard {r['shard_index']}: {r['selected_items']} tests in {len(r['selected_files'])} files")
    errors = check(reports)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if not errors:
        print(f"OK: {len(reports)} shards ran all {reports[0]['collected_items']} collected tests, each file exactly once")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
