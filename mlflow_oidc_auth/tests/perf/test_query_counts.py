"""Query-count characterization and regression tests (issue #253).

Each test asserts the number of SQL statements a resolver path issues. They are
written as exact assertions so that a regression AND a silent improvement both fail,
forcing the number in the diff to be updated deliberately.

See conftest.py for why round-trips (not query cost) are the metric.
"""

import pytest
from mlflow.exceptions import MlflowException


class TestUserGroupLookups:
    """The user -> groups helpers used by every group-scoped permission check."""

    def test_list_groups_for_user_is_single_query(self, seeded_store, counter):
        """Resolving a user's group names must not fan out into separate lookups.

        Was 3 statements: get_user, then user_groups by user_id, then groups by id IN (...).
        """
        store, username, group_names = seeded_store
        counter.reset()

        names = store.group_repo.list_groups_for_user(username)

        assert sorted(names) == sorted(group_names)
        assert counter.count == 1, counter.report()

    def test_list_group_ids_for_user_is_single_query(self, seeded_store, counter):
        """Was 2 statements: get_user, then user_groups by user_id."""
        store, username, _ = seeded_store
        counter.reset()

        ids = store.group_repo.list_group_ids_for_user(username)

        assert len(ids) == 8
        assert counter.count == 1, counter.report()

    def test_group_lookup_is_constant_in_group_count(self, store, counter):
        """Group resolution must not scale with how many groups the user belongs to."""
        counts = {}
        for n_groups in (1, 4, 8):
            username = f"user{n_groups}@example.com"
            groups = [f"g{n_groups}-{i}" for i in range(n_groups)]
            store.create_user(username, "pw", username)
            store.populate_groups(groups)
            store.set_user_groups(username, groups)

            counter.reset()
            store.group_repo.list_groups_for_user(username)
            counts[n_groups] = counter.count

        assert len(set(counts.values())) == 1, f"not constant in group count: {counts}"


class TestGroupPermissionResolution:
    """The per-resource group permission check — the hottest path in the resolver."""

    def _grant(self, store, group, exp_id, permission):
        store.create_group_experiment_permission(group, exp_id, permission)

    def test_group_permission_check_is_single_query(self, seeded_store, counter):
        """Was 3 + 2G statements (19 at G=8): a per-group loop, each re-resolving the group.

        The user must get the highest permission across all their groups in one query.
        """
        store, username, groups = seeded_store
        self._grant(store, groups[1], "exp-1", "READ")
        self._grant(store, groups[4], "exp-1", "MANAGE")
        self._grant(store, groups[6], "exp-1", "EDIT")
        counter.reset()

        perm = store.experiment_group_repo.get_group_permission_for_user_resource("exp-1", username)

        assert perm is not None
        assert perm.permission == "MANAGE", "must resolve to the highest permission across groups"
        assert counter.count == 1, counter.report()

    def test_group_permission_check_is_constant_in_group_count(self, store, counter):
        """The check must be O(1) in group membership, not O(G)."""
        counts = {}
        for n_groups in (1, 4, 8):
            username = f"perm{n_groups}@example.com"
            groups = [f"pg{n_groups}-{i}" for i in range(n_groups)]
            store.create_user(username, "pw", username)
            store.populate_groups(groups)
            store.set_user_groups(username, groups)
            store.create_group_experiment_permission(groups[0], f"exp-{n_groups}", "READ")

            counter.reset()
            store.experiment_group_repo.get_group_permission_for_user_resource(f"exp-{n_groups}", username)
            counts[n_groups] = counter.count

        assert len(set(counts.values())) == 1, f"query count scales with group membership: {counts}"

    def test_group_permission_miss_is_single_query(self, seeded_store, counter):
        """A miss (no group grants anything) is the common case in a search-filter pass."""
        store, username, _ = seeded_store
        counter.reset()

        with pytest.raises(MlflowException):
            store.experiment_group_repo.get_group_permission_for_user_resource("exp-unknown", username)

        assert counter.count == 1, counter.report()


class TestFilterPassScaling:
    """A search/list request resolves permissions for many resources in one pass."""

    @pytest.mark.parametrize("n_resources", [1, 10, 25])
    def test_group_checks_scale_linearly_with_one_query_each(self, seeded_store, counter, n_resources):
        """Per-resource cost must be exactly one query, so a filter pass is O(N) not O(N*G)."""
        store, username, _ = seeded_store
        counter.reset()

        for i in range(n_resources):
            with pytest.raises(MlflowException):
                store.experiment_group_repo.get_group_permission_for_user_resource(f"exp-{i}", username)

        assert counter.count == n_resources, counter.report()
