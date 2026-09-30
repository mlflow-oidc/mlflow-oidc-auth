"""Tests for the CI test-sharding helpers (``_sharding.py`` and ``scripts/ci/check_shards.py``)."""

import hashlib
import importlib.util
from collections import OrderedDict
from pathlib import Path

from mlflow_oidc_auth.tests._sharding import assign_files

_CHECK_SHARDS = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "check_shards.py"


def _load_check_shards():
    spec = importlib.util.spec_from_file_location("check_shards", _CHECK_SHARDS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _files(n: int) -> "OrderedDict[str, int]":
    return OrderedDict((f"dir/test_{i:02d}.py", i + 1) for i in range(n))


def test_every_file_lands_in_exactly_one_shard():
    files = _files(23)
    shards = assign_files(files, {}, 4)
    assigned = [path for shard in shards for path in shard]
    assert sorted(assigned) == sorted(files)
    assert len(assigned) == len(set(assigned))


def test_assignment_ignores_collection_order():
    files = _files(17)
    reversed_files = OrderedDict(reversed(list(files.items())))
    weights = {"dir/test_03.py": 50.0}
    assert assign_files(files, weights, 3) == assign_files(reversed_files, weights, 3)


def test_unweighted_new_file_is_still_assigned():
    files = _files(5)
    files["dir/test_brand_new.py"] = 1
    weights = {path: 10.0 for path in list(files)[:5]}
    shards = assign_files(files, weights, 2)
    assert sum("dir/test_brand_new.py" in shard for shard in shards) == 1


def test_weights_balance_the_shards():
    files = OrderedDict((f"t{i}.py", 1) for i in range(6))
    weights = {"t0.py": 60.0, "t1.py": 30.0, "t2.py": 30.0, "t3.py": 20.0, "t4.py": 20.0, "t5.py": 20.0}
    shards = assign_files(files, weights, 2)
    loads = [sum(weights[p] for p in shard) for shard in shards]
    # Greedy longest-first: the spread never exceeds the smallest file's weight here.
    assert max(loads) - min(loads) <= 20.0
    assert "t0.py" in shards[0] and "t0.py" not in shards[1]


def test_more_shards_than_files_leaves_empty_shards():
    shards = assign_files(_files(2), {}, 4)
    assert sorted(len(s) for s in shards) == [0, 0, 1, 1]


def _reports(file_items, shards):
    all_files = sorted(file_items)
    digest = hashlib.sha256("\n".join(all_files).encode()).hexdigest()
    return [
        {
            "shard_count": len(shards),
            "shard_index": i,
            "collected_items": sum(file_items.values()),
            "collected_files": len(all_files),
            "collected_files_sha256": digest,
            "selected_items": sum(file_items[p] for p in shard),
            "selected_files": shard,
        }
        for i, shard in enumerate(shards)
    ]


def test_check_shards_accepts_a_partition():
    file_items = {"a.py": 2, "b.py": 3, "c.py": 1}
    assert _load_check_shards().check(_reports(file_items, [["a.py"], ["b.py", "c.py"]])) == []


def test_check_shards_rejects_a_missing_shard():
    file_items = {"a.py": 2, "b.py": 3, "c.py": 1}
    reports = _reports(file_items, [["a.py"], ["b.py", "c.py"]])[:1]
    assert _load_check_shards().check(reports)


def test_check_shards_rejects_a_file_run_twice():
    file_items = {"a.py": 2, "b.py": 3}
    reports = _reports(file_items, [["a.py", "b.py"], ["b.py"]])
    errors = _load_check_shards().check(reports)
    assert any("b.py ran in shard 0 and shard 1" in e for e in errors)


def test_check_shards_rejects_a_dropped_file():
    file_items = {"a.py": 2, "b.py": 3, "c.py": 1}
    reports = _reports(file_items, [["a.py"], ["b.py"]])
    assert _load_check_shards().check(reports)


def test_check_shards_rejects_shards_that_collected_different_suites():
    reports = _reports({"a.py": 2, "b.py": 3}, [["a.py"], ["b.py"]])
    reports[1]["collected_items"] = 99
    assert _load_check_shards().check(reports)


def test_check_shards_rejects_no_reports():
    assert _load_check_shards().check([])
