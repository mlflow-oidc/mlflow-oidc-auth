"""Split the test suite into deterministic shards so CI can run them as parallel jobs.

Hooked into pytest from ``conftest.py``. Without ``--shard-count`` nothing changes: every
collected test runs, exactly as before.

With ``--shard-count=N --shard-index=K`` (use the ``=`` form: the options are registered from
``conftest.py``, after pytest's first pass over the command line) every shard collects the
*whole* suite (so collection, marker deselection and module import side effects are identical to
a single-process run), then keeps only the test files assigned to shard ``K``. Assignment is per file, never per test, so a
module's fixtures and its test-order assumptions stay inside one process.

Files are balanced with a greedy longest-first assignment using the per-file weights (seconds)
in ``shard_weights.json``. A file that is missing from that map is weighted by its test count,
so a new test file is still assigned to exactly one shard — the weights only affect balance,
never coverage. Refresh the map when the balance drifts (see ``docs/development.md``).

``--shard-report PATH`` writes what this shard collected and selected as JSON. The CI aggregator
reads every shard's report and fails unless the shards agree on the full collection and their
selections partition it exactly (``scripts/ci/check_shards.py``).
"""

import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List

import pytest

WEIGHTS_FILE = Path(__file__).with_name("shard_weights.json")

# Weight, in seconds, of one test in a file that has no entry in ``shard_weights.json``.
DEFAULT_SECONDS_PER_TEST = 0.1


def add_shard_options(parser: pytest.Parser) -> None:
    """Register the sharding options.

    Parameters:
        parser: The pytest command-line parser.
    """
    group = parser.getgroup("sharding", "split the suite into deterministic per-file shards")
    group.addoption("--shard-count", type=int, default=None, help="total number of shards")
    group.addoption("--shard-index", type=int, default=None, help="zero-based index of the shard to run")
    group.addoption("--shard-report", default=None, help="write this shard's collection summary as JSON to PATH")


def _load_weights() -> Dict[str, float]:
    """Return the committed per-file weights, keyed by path relative to the tests directory.

    Returns:
        A mapping of test file path to its measured duration in seconds; empty if the file is absent.
    """
    if not WEIGHTS_FILE.exists():
        return {}
    return {str(k): float(v) for k, v in json.loads(WEIGHTS_FILE.read_text()).items()}


def assign_files(file_tests: "OrderedDict[str, int]", weights: Dict[str, float], shard_count: int) -> List[List[str]]:
    """Assign every test file to exactly one shard, balancing the total weight.

    Parameters:
        file_tests: Test file path to number of selected tests in it.
        weights: Test file path to measured duration in seconds.
        shard_count: Number of shards.

    Returns:
        One sorted list of file paths per shard. Every file appears in exactly one list.

    Raises:
        AssertionError: If the result is not an exact partition of ``file_tests``.
    """

    def weight(path: str) -> float:
        return weights.get(path, file_tests[path] * DEFAULT_SECONDS_PER_TEST)

    shards: List[List[str]] = [[] for _ in range(shard_count)]
    loads = [0.0] * shard_count
    # Heaviest first; path breaks ties so the result never depends on collection order.
    for path in sorted(file_tests, key=lambda p: (-weight(p), p)):
        target = min(range(shard_count), key=lambda i: (loads[i], i))
        shards[target].append(path)
        loads[target] += weight(path)

    assigned = [path for shard in shards for path in shard]
    assert len(assigned) == len(set(assigned)) == len(file_tests), "shard assignment is not a partition of the collected files"
    assert set(assigned) == set(file_tests), "shard assignment is not a partition of the collected files"
    return [sorted(shard) for shard in shards]


def select_shard(session: pytest.Session, config: pytest.Config, items: List[pytest.Item]) -> None:
    """Keep only the tests in this shard's files; runs after marker/keyword deselection.

    Parameters:
        session: The pytest session.
        config: The pytest config.
        items: The collected (and already marker-filtered) test items, modified in place.

    Raises:
        pytest.UsageError: If the shard options are incomplete or out of range.
    """
    shard_count = config.getoption("--shard-count")
    shard_index = config.getoption("--shard-index")
    if shard_count is None and shard_index is None:
        return
    if shard_count is None or shard_index is None or shard_count < 1 or not 0 <= shard_index < shard_count:
        raise pytest.UsageError("--shard-count and --shard-index must be given together, with 0 <= index < count")

    tests_root = Path(__file__).parent
    file_tests: "OrderedDict[str, int]" = OrderedDict()
    item_file: List[str] = []
    for item in items:
        path = Path(str(item.path)).resolve().relative_to(tests_root.resolve()).as_posix()
        file_tests[path] = file_tests.get(path, 0) + 1
        item_file.append(path)

    shards = assign_files(file_tests, _load_weights(), shard_count)
    mine = set(shards[shard_index])
    selected = [item for item, path in zip(items, item_file) if path in mine]
    deselected = [item for item, path in zip(items, item_file) if path not in mine]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = selected

    report_path = config.getoption("--shard-report")
    if report_path:
        all_files = sorted(file_tests)
        report = {
            "shard_count": shard_count,
            "shard_index": shard_index,
            "collected_items": len(item_file),
            "collected_files_sha256": hashlib.sha256("\n".join(all_files).encode()).hexdigest(),
            "collected_files": len(all_files),
            "selected_items": len(selected),
            "selected_files": shards[shard_index],
            "selected_file_items": {path: file_tests[path] for path in shards[shard_index]},
        }
        Path(report_path).write_text(json.dumps(report, indent=2))
