"""Query-count characterization and regression tests (issue #253).

Each test asserts the number of SQL statements a resolver path issues. They are
written as exact assertions so that a regression AND a silent improvement both fail,
forcing the number in the diff to be updated deliberately.

See conftest.py for why round-trips (not query cost) are the metric.
"""

from types import SimpleNamespace

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


class TestFoldedQueriesDoNotOverGrant:
    """The folded group queries must never grant beyond the caller's own memberships.

    These are real-DB authorization tests, not query-count tests. They exist because
    dropping the `username` predicate from a folded JOIN — the maximal over-grant — is
    invisible to a mock-chain test and previously passed the entire suite.
    """

    def test_experiment_fold_ignores_groups_the_user_is_not_in(self, store, counter):
        store.create_user("owner@example.com", "pw", "Owner")
        store.create_user("outsider@example.com", "pw", "Outsider")
        store.populate_groups(["insiders", "outsiders"])
        store.set_user_groups("owner@example.com", ["insiders"])
        store.set_user_groups("outsider@example.com", ["outsiders"])
        # Only the group the outsider is NOT in has a grant.
        store.create_group_experiment_permission("insiders", "exp-secret", "MANAGE")

        with pytest.raises(MlflowException):
            store.experiment_group_repo.get_group_permission_for_user_resource("exp-secret", "outsider@example.com")

        owner = store.experiment_group_repo.get_group_permission_for_user_resource("exp-secret", "owner@example.com")
        assert owner.permission == "MANAGE"

    def test_registered_model_fold_ignores_groups_the_user_is_not_in(self, store):
        store.create_user("mowner@example.com", "pw", "M Owner")
        store.create_user("moutsider@example.com", "pw", "M Outsider")
        store.populate_groups(["m-insiders", "m-outsiders"])
        store.set_user_groups("mowner@example.com", ["m-insiders"])
        store.set_user_groups("moutsider@example.com", ["m-outsiders"])
        store.create_group_model_permission("m-insiders", "secret-model", "MANAGE")

        with pytest.raises(MlflowException):
            store.registered_model_group_repo.get_for_user("secret-model", "moutsider@example.com")

        owner = store.registered_model_group_repo.get_for_user("secret-model", "mowner@example.com")
        assert owner.permission == "MANAGE"

    def test_registered_model_fold_keys_on_the_model_name(self, store):
        """The resource predicate must survive the fold — a grant on one model is not another."""
        store.create_user("m2@example.com", "pw", "M2")
        store.populate_groups(["m2-group"])
        store.set_user_groups("m2@example.com", ["m2-group"])
        store.create_group_model_permission("m2-group", "model-a", "MANAGE")

        assert store.registered_model_group_repo.get_for_user("model-a", "m2@example.com").permission == "MANAGE"
        with pytest.raises(MlflowException):
            store.registered_model_group_repo.get_for_user("model-b", "m2@example.com")

    def test_scorer_fold_ignores_groups_the_user_is_not_in(self, store):
        store.create_user("sowner@example.com", "pw", "S Owner")
        store.create_user("soutsider@example.com", "pw", "S Outsider")
        store.populate_groups(["s-insiders", "s-outsiders"])
        store.set_user_groups("sowner@example.com", ["s-insiders"])
        store.set_user_groups("soutsider@example.com", ["s-outsiders"])
        store.create_group_scorer_permission("s-insiders", "exp-1", "scorer-x", "MANAGE")

        with pytest.raises(MlflowException):
            store.scorer_group_repo.get_group_permission_for_user_scorer("exp-1", "scorer-x", "soutsider@example.com")

        owner = store.scorer_group_repo.get_group_permission_for_user_scorer("exp-1", "scorer-x", "sowner@example.com")
        assert owner.permission == "MANAGE"

    def test_scorer_fold_keys_on_both_experiment_and_scorer_name(self, store):
        """The scorer fold has a 2-part key; both predicates must survive."""
        store.create_user("s2@example.com", "pw", "S2")
        store.populate_groups(["s2-group"])
        store.set_user_groups("s2@example.com", ["s2-group"])
        store.create_group_scorer_permission("s2-group", "exp-1", "scorer-x", "MANAGE")

        assert store.scorer_group_repo.get_group_permission_for_user_scorer("exp-1", "scorer-x", "s2@example.com").permission == "MANAGE"
        with pytest.raises(MlflowException):  # same scorer name, different experiment
            store.scorer_group_repo.get_group_permission_for_user_scorer("exp-2", "scorer-x", "s2@example.com")
        with pytest.raises(MlflowException):  # same experiment, different scorer
            store.scorer_group_repo.get_group_permission_for_user_scorer("exp-1", "scorer-y", "s2@example.com")


class TestPermissionContextBuild:
    """build_user_permission_context backs the admin/listing batch paths."""

    def test_context_build_has_no_redundant_identity_lookups(self, seeded_store, counter):
        """Each pre-fetch used to re-resolve the same user (7x) and memberships (3x).

        Folding those into JOINs took the build from 20 statements to 15. The assertion
        is exact so a regression, or a further improvement, has to be acknowledged.
        """
        store, username, _ = seeded_store
        import mlflow_oidc_auth.utils.batch_permissions as bp

        original = bp.store
        bp.store = store
        try:
            counter.reset()
            ctx = bp.build_user_permission_context(username)
        finally:
            bp.store = original

        assert ctx.username == username
        assert counter.count == 15, counter.report()

    def test_context_build_is_constant_in_group_count(self, store, counter):
        counts = {}
        import mlflow_oidc_auth.utils.batch_permissions as bp

        original = bp.store
        bp.store = store
        try:
            for n_groups in (1, 4, 8):
                username = f"ctx{n_groups}@example.com"
                groups = [f"cg{n_groups}-{i}" for i in range(n_groups)]
                store.create_user(username, "pw", username)
                store.populate_groups(groups)
                store.set_user_groups(username, groups)

                counter.reset()
                bp.build_user_permission_context(username)
                counts[n_groups] = counter.count
        finally:
            bp.store = original

        assert len(set(counts.values())) == 1, f"context build scales with group count: {counts}"


class TestWorkspaceFallbackMemo:
    """The workspace fallback must be resolved once per batch, not once per resource."""

    def test_workspace_deny_does_not_scale_with_resource_count(self, seeded_store, counter, monkeypatch):
        """get_workspace_permission_cached never caches DENIALS.

        Without a memo, a user with no workspace grant re-ran the full source walk for
        every resource, making a listing 21+9N queries. The memo lives on the context, so
        its lifetime is one batch call and it cannot serve a stale decision.
        """
        store, username, _ = seeded_store
        import mlflow_oidc_auth.utils.batch_permissions as bp
        from mlflow_oidc_auth.config import config as cfg

        import mlflow_oidc_auth.store as store_mod
        import mlflow_oidc_auth.utils.workspace_cache as wsc

        monkeypatch.setattr(cfg, "MLFLOW_ENABLE_WORKSPACES", True)
        monkeypatch.setattr("mlflow.utils.workspace_context.get_request_workspace", lambda: "ws-none")
        # workspace_cache resolves through the store singleton, not bp.store.
        monkeypatch.setattr(store_mod, "store", store)
        wsc.flush_workspace_cache()

        original = bp.store
        bp.store = store
        try:
            counts = {}
            for n in (1, 5, 20):
                experiments = [SimpleNamespace(experiment_id=f"e{i}", name=f"exp-{i}") for i in range(n)]
                ctx = bp.build_user_permission_context(username)
                counter.reset()
                for exp in experiments:
                    bp.resolve_experiment_permission_from_context(ctx, exp.experiment_id, exp.name)
                counts[n] = counter.count
        finally:
            bp.store = original

        finally_counts = counts
        assert len(set(finally_counts.values())) == 1, f"workspace deny cost scales with resource count: {finally_counts}"
        # And it must actually be walking the sources, or the test proves nothing.
        assert next(iter(finally_counts.values())) > 0, "deny path issued no queries; test would be vacuous"


class TestListFoldsDoNotLeakAcrossUsers:
    """The three JOIN folds gate cross-user isolation; nothing else tests their predicates.

    Neutering the username predicate or the join column in any of these leaks another
    user's permissions, and the rest of the suite stays green — so these are the only
    guard against that.
    """

    def _seed_two_users(self, store):
        store.create_user("victim@example.com", "pw", "Victim")
        store.create_user("alice@example.com", "pw", "Alice")
        # Decoy groups first so membership-row PKs diverge from group ids — otherwise a
        # join on the wrong column (SqlUserGroup.id instead of .group_id) is invisible.
        store.populate_groups(["decoy-a", "decoy-b", "decoy-c", "victim-grp", "alice-grp"])
        store.set_user_groups("victim@example.com", ["victim-grp"])
        store.set_user_groups("alice@example.com", ["alice-grp"])
        # A grant on a decoy group neither user belongs to, whose group id collides with
        # the membership row PKs, so a wrong-column join surfaces it.
        store.create_group_experiment_permission("decoy-a", "exp-decoy", "MANAGE")

    def test_list_permissions_for_user_returns_only_the_callers_rows(self, store):
        self._seed_two_users(store)
        store.create_experiment_permission("exp-secret", "victim@example.com", "MANAGE")

        assert [p.experiment_id for p in store.experiment_repo.list_permissions_for_user("victim@example.com")] == ["exp-secret"]
        assert store.experiment_repo.list_permissions_for_user("alice@example.com") == []

    def test_list_permissions_for_user_groups_returns_only_the_callers_groups(self, store):
        self._seed_two_users(store)
        store.create_group_experiment_permission("victim-grp", "exp-secret", "MANAGE")

        victim = store.experiment_group_repo.list_permissions_for_user_groups("victim@example.com")
        assert [p.experiment_id for p in victim] == ["exp-secret"], "wrong rows for the caller"
        assert store.experiment_group_repo.list_permissions_for_user_groups("alice@example.com") == []

    def test_list_regex_for_user_returns_only_the_callers_rows(self, store):
        self._seed_two_users(store)
        store.create_experiment_regex_permission("^secret/.*", 1, "MANAGE", "victim@example.com")

        assert len(store.experiment_regex_repo.list_regex_for_user("victim@example.com")) == 1
        assert store.experiment_regex_repo.list_regex_for_user("alice@example.com") == []

    def test_group_regex_fold_uses_group_id_not_the_membership_row_id(self, store):
        """Regression for the join-table-PK bug: membership row PK != group id.

        Seeded so the two diverge, so using the wrong column returns a non-member group.
        """
        store.create_user("carol@example.com", "pw", "Carol")
        groups = [f"grp{i}" for i in range(6)]
        store.populate_groups(groups)
        store.set_user_groups("carol@example.com", ["grp5"])  # membership row PK 1, group id 6
        # Grant on a group carol is NOT in, whose id collides with her membership row PK.
        store.create_group_experiment_regex_permission("grp0", ".*", 1, "MANAGE")

        rows = store.experiment_group_regex_repo.list_permissions_for_user_groups("carol@example.com")
        assert rows == [], f"leaked a grant from a non-member group: {[(r.group_id, r.permission) for r in rows]}"


class TestGroupPermissionCollapse:
    """Multiple group grants on one resource must resolve deterministically."""

    def test_batch_and_per_resource_paths_agree(self, store):
        """The batch path used a last-wins dict; the per-resource path folds by precedence."""
        import mlflow_oidc_auth.utils.batch_permissions as bp

        store.create_user("dora@example.com", "pw", "Dora")
        store.populate_groups(["hi", "lo"])
        store.set_user_groups("dora@example.com", ["hi", "lo"])
        store.create_group_experiment_permission("hi", "e0", "MANAGE")
        store.create_group_experiment_permission("lo", "e0", "READ")

        per_resource = store.experiment_group_repo.get_group_permission_for_user_resource("e0", "dora@example.com").permission

        original = bp.store
        bp.store = store
        try:
            batch = bp.build_user_permission_context("dora@example.com").group_experiment_permissions["e0"]
        finally:
            bp.store = original

        assert batch == per_resource, "batch and per-resource paths disagree on multi-group resolution"

    def test_collapse_is_independent_of_membership_order(self, store):
        import mlflow_oidc_auth.utils.batch_permissions as bp

        store.create_user("eve@example.com", "pw", "Eve")
        store.populate_groups(["ga", "gz"])
        store.create_group_experiment_permission("ga", "e0", "MANAGE")
        store.create_group_experiment_permission("gz", "e0", "READ")

        original = bp.store
        bp.store = store
        try:
            results = []
            for order in (["ga", "gz"], ["gz", "ga"]):
                store.set_user_groups("eve@example.com", order)
                results.append(bp.build_user_permission_context("eve@example.com").group_experiment_permissions["e0"])
        finally:
            bp.store = original

        assert results[0] == results[1], f"resolution depends on membership insertion order: {results}"
