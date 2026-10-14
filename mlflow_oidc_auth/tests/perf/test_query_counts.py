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
            store.create_user(username, username)
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
            store.create_user(username, username)
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
        store.create_user("owner@example.com", "Owner")
        store.create_user("outsider@example.com", "Outsider")
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
        store.create_user("mowner@example.com", "M Owner")
        store.create_user("moutsider@example.com", "M Outsider")
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
        store.create_user("m2@example.com", "M2")
        store.populate_groups(["m2-group"])
        store.set_user_groups("m2@example.com", ["m2-group"])
        store.create_group_model_permission("m2-group", "model-a", "MANAGE")

        assert store.registered_model_group_repo.get_for_user("model-a", "m2@example.com").permission == "MANAGE"
        with pytest.raises(MlflowException):
            store.registered_model_group_repo.get_for_user("model-b", "m2@example.com")

    def test_scorer_fold_ignores_groups_the_user_is_not_in(self, store):
        store.create_user("sowner@example.com", "S Owner")
        store.create_user("soutsider@example.com", "S Outsider")
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
        store.create_user("s2@example.com", "S2")
        store.populate_groups(["s2-group"])
        store.set_user_groups("s2@example.com", ["s2-group"])
        store.create_group_scorer_permission("s2-group", "exp-1", "scorer-x", "MANAGE")

        assert store.scorer_group_repo.get_group_permission_for_user_scorer("exp-1", "scorer-x", "s2@example.com").permission == "MANAGE"
        with pytest.raises(MlflowException):  # same scorer name, different experiment
            store.scorer_group_repo.get_group_permission_for_user_scorer("exp-2", "scorer-x", "s2@example.com")
        with pytest.raises(MlflowException):  # same experiment, different scorer
            store.scorer_group_repo.get_group_permission_for_user_scorer("exp-1", "scorer-y", "s2@example.com")


def _read_all(ctx, resource_types):
    """Read every grant a bulk context resolves ``resource_types`` against: direct grants and patterns."""
    for resource_type in resource_types:
        ctx.direct(resource_type)
        ctx.patterns(resource_type)
    return ctx


class TestPermissionContextBuild:
    """The batch context backs the admin/listing batch paths (the grant context since issue #460)."""

    TYPES = ("experiment", "registered_model", "prompt")

    def test_context_build_has_no_redundant_identity_lookups(self, seeded_store, counter, monkeypatch):
        """Reading the experiment, model and prompt grants the old build fetched, without identity lookups.

        Each read used to re-resolve the same user (7x) and memberships (3x); folding those into
        JOINs took the old build from 20 statements to 15, and the model and prompt pattern lists
        JOINing too (#459) to 13. The grant context reads the group ids once, each type's two
        pattern lists, and the direct grants once per grant table — prompts share the
        registered-model read: 11. The assertion is exact so a regression, or a further
        improvement, has to be acknowledged.
        """
        import mlflow_oidc_auth.store as store_mod
        import mlflow_oidc_auth.utils.batch_permissions as bp

        store, username, _ = seeded_store
        monkeypatch.setattr(store_mod, "store", store)
        counter.reset()
        ctx = _read_all(bp.build_user_permission_context(username), self.TYPES)

        assert ctx.username == username
        assert counter.count == 11, counter.report()

    def test_context_build_is_constant_in_group_count(self, store, counter, monkeypatch):
        import mlflow_oidc_auth.store as store_mod
        import mlflow_oidc_auth.utils.batch_permissions as bp

        monkeypatch.setattr(store_mod, "store", store)
        counts = {}
        for n_groups in (1, 4, 8):
            username = f"ctx{n_groups}@example.com"
            groups = [f"cg{n_groups}-{i}" for i in range(n_groups)]
            store.create_user(username, username)
            store.populate_groups(groups)
            store.set_user_groups(username, groups)

            counter.reset()
            _read_all(bp.build_user_permission_context(username), self.TYPES)
            counts[n_groups] = counter.count

        assert len(set(counts.values())) == 1, f"context build scales with group count: {counts}"


class TestWorkspaceFallbackMemo:
    """The workspace fallback must be resolved once per batch, not once per resource."""

    def test_workspace_deny_does_not_scale_with_resource_count(self, seeded_store, counter, monkeypatch):
        """The batch memo bounds a denied user's workspace check to one per batch.

        Before issue #456 get_workspace_permission_cached never cached DENIALS, so without
        a memo a user with no workspace grant re-ran the full source walk for every
        resource, making a listing 21+9N queries. Denials are cached now; the workspace
        cache is flushed before each batch below so this still measures the memo alone.
        The memo lives on the context, so its lifetime is one batch call.
        """
        store, username, _ = seeded_store
        import mlflow_oidc_auth.utils.batch_permissions as bp
        from mlflow_oidc_auth.config import config as cfg

        import mlflow_oidc_auth.store as store_mod
        import mlflow_oidc_auth.utils.workspace_cache as wsc

        monkeypatch.setattr(cfg, "MLFLOW_ENABLE_WORKSPACES", True)
        monkeypatch.setattr("mlflow.utils.workspace_context.get_request_workspace", lambda: "ws-none")
        # The grant context and workspace_cache both resolve through the store singleton.
        monkeypatch.setattr(store_mod, "store", store)
        wsc.flush_workspace_cache()

        counts = {}
        for n in (1, 5, 20):
            # Experiments of the request's workspace, as MLflow's search returns them.
            experiments = [SimpleNamespace(experiment_id=f"e{i}", name=f"exp-{i}", workspace="ws-none") for i in range(n)]
            ctx = _read_all(bp.build_user_permission_context(username), ("experiment",))
            wsc.flush_workspace_cache()
            counter.reset()
            for exp in experiments:
                bp.resolve_experiment_permission_from_context(ctx, exp.experiment_id, exp.name, exp.workspace)
            counts[n] = counter.count

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
        store.create_user("victim@example.com", "Victim")
        store.create_user("alice@example.com", "Alice")
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
        store.create_user("carol@example.com", "Carol")
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

        store.create_user("dora@example.com", "Dora")
        store.populate_groups(["hi", "lo"])
        store.set_user_groups("dora@example.com", ["hi", "lo"])
        store.create_group_experiment_permission("hi", "e0", "MANAGE")
        store.create_group_experiment_permission("lo", "e0", "READ")

        per_resource = store.experiment_group_repo.get_group_permission_for_user_resource("e0", "dora@example.com").permission

        import mlflow_oidc_auth.store as store_mod

        original = store_mod.store
        store_mod.store = store
        try:
            batch = bp.build_user_permission_context("dora@example.com").direct("experiment").group["e0"]
        finally:
            store_mod.store = original

        assert batch == per_resource, "batch and per-resource paths disagree on multi-group resolution"

    def test_collapse_is_independent_of_membership_order(self, store):
        import mlflow_oidc_auth.utils.batch_permissions as bp

        store.create_user("eve@example.com", "Eve")
        store.populate_groups(["ga", "gz"])
        store.create_group_experiment_permission("ga", "e0", "MANAGE")
        store.create_group_experiment_permission("gz", "e0", "READ")

        import mlflow_oidc_auth.store as store_mod

        original = store_mod.store
        store_mod.store = store
        try:
            results = []
            for order in (["ga", "gz"], ["gz", "ga"]):
                store.set_user_groups("eve@example.com", order)
                results.append(bp.build_user_permission_context("eve@example.com").direct("experiment").group["e0"])
        finally:
            store_mod.store = original

        assert results[0] == results[1], f"resolution depends on membership insertion order: {results}"


class TestSearchRepaging:
    """The re-paging loop must consume every fetched row (issue #456).

    It used to slice the UNFILTERED batch to the page's free space before filtering, then
    advance the token by the slice, so the discarded tail was fetched again: 8 MLflow
    search calls where 6 suffice at 10% visibility. The count includes MLflow's own
    first-page call.
    """

    def _page_once(self, kind, rows):
        from mlflow_oidc_auth.tests.search_paging_helpers import FakeSearchStore, row_id, run_filtered_page

        store = FakeSearchStore(rows)
        visible = {row_id(kind, r) for i, r in enumerate(rows) if i % 10 == 0}  # 10% visibility, spread evenly
        ids, token = run_filtered_page(kind, store, lambda rid: rid in visible, max_results=100, page_token=None)
        return store, visible, ids, token

    def test_search_experiments_repaging_calls_minimum(self):
        from mlflow_oidc_auth.tests.search_paging_helpers import make_experiments

        store, visible, ids, token = self._page_once("experiments", make_experiments(500))

        assert sorted(ids) == sorted(visible), "page must hold every readable row (50 < max_results)"
        assert token == "", "result set exhausted"
        assert store.calls <= 6, f"search_experiments called {store.calls} times"

    def test_search_registered_models_repaging_calls_minimum(self):
        from mlflow_oidc_auth.tests.search_paging_helpers import make_registered_models

        store, visible, ids, token = self._page_once("registered_models", make_registered_models(500))

        assert sorted(ids) == sorted(visible)
        assert token == ""
        assert store.calls <= 6, f"search_registered_models called {store.calls} times"


class TestWorkspaceDenialCache:
    """A denied user's workspace check must be answered from cache once warm (issue #456)."""

    def test_workspace_denial_warm_zero_statements(self, seeded_store, counter, monkeypatch):
        store, username, _ = seeded_store
        import mlflow_oidc_auth.store as store_mod
        import mlflow_oidc_auth.utils.workspace_cache as wsc
        from mlflow_oidc_auth.config import config as cfg

        monkeypatch.setattr(cfg, "MLFLOW_ENABLE_WORKSPACES", True)
        monkeypatch.setattr(store_mod, "store", store)
        wsc.flush_workspace_cache()
        try:
            counter.reset()
            assert wsc.get_workspace_permission_cached(username, "ws-none") is None
            assert counter.count > 0, "cold denial issued no statements; test would be vacuous"

            counter.reset()
            assert wsc.get_workspace_permission_cached(username, "ws-none") is None
            assert counter.count == 0, counter.report()
        finally:
            wsc.flush_workspace_cache()


class TestSearchFilterStatements:
    """A search filter's auth-DB cost must not grow with the rows it scans (issue #460).

    Each listed row used to be resolved through the per-resource path: about five statements per
    scanned row on a cold cache (2,355 for 500 experiments at 10% visibility). The filters now
    resolve every row in memory against the caller's grant context, read once per resource type.
    """

    USERNAME = "reader@example.com"

    @pytest.fixture
    def grants(self, store, monkeypatch):
        """A non-admin in 5 groups, with grants on 10% of the rows and patterns that match none."""
        import mlflow_oidc_auth.store as store_module
        from mlflow_oidc_auth.config import config

        monkeypatch.setattr(store_module, "store", store)
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
        groups = [f"team-{i}" for i in range(5)]
        store.create_user(self.USERNAME, "Reader")
        store.populate_groups(groups)
        store.set_user_groups(self.USERNAME, groups)
        for i in range(0, 500, 20):
            store.create_experiment_permission(str(i), self.USERNAME, "READ")
            store.create_registered_model_permission(f"model-{i}", self.USERNAME, "READ")
        for i in range(10, 500, 20):
            store.create_group_experiment_permission(groups[i % 5], str(i), "READ")
            store.create_group_model_permission(groups[i % 5], f"model-{i}", "READ")
        store.create_experiment_regex_permission("^no-such-experiment", 1, "MANAGE", self.USERNAME)
        store.create_group_experiment_regex_permission(groups[0], "^no-such-experiment", 1, "MANAGE")
        store.create_registered_model_regex_permission("^no-such-model", 1, "MANAGE", self.USERNAME)
        store.create_group_registered_model_regex_permission(groups[0], "^no-such-model", 1, "MANAGE")
        return store

    def _filter(self, kind, rows):
        """Serve one request: MLflow's unfiltered first page, then the plugin's filter, for real."""
        import json
        from contextlib import ExitStack
        from unittest.mock import patch

        from flask import Flask, Response
        from mlflow.utils.proto_json_utils import message_to_json

        import mlflow_oidc_auth.hooks.after_request as ar
        from mlflow_oidc_auth.tests.search_paging_helpers import _KINDS, FakeSearchStore

        request_cls, field, method, _ident, filter_name, _seam = _KINDS[kind]
        fake = FakeSearchStore(rows)
        first = getattr(fake, method)(max_results=100, page_token=None)
        response = request_cls.Response()
        getattr(response, field).extend([row.to_proto() for row in first])
        if first.token:
            response.next_page_token = first.token
        resp = Response(message_to_json(response), mimetype="application/json")
        target = "mlflow_oidc_auth.hooks.after_request"
        with ExitStack() as stack:
            stack.enter_context(Flask(__name__).test_request_context())
            stack.enter_context(patch(f"{target}.get_fastapi_admin_status", return_value=False))
            stack.enter_context(patch(f"{target}.get_fastapi_username", return_value=self.USERNAME))
            stack.enter_context(patch(f"{target}._get_request_message", return_value=request_cls(max_results=100)))
            stack.enter_context(patch(f"{target}._get_tracking_store", return_value=fake))
            stack.enter_context(patch(f"{target}._get_model_registry_store", return_value=fake))
            getattr(ar, filter_name)(resp)
        return json.loads(resp.get_data(as_text=True)).get(field, [])

    def _cold_count(self, counter, kind, rows):
        from mlflow_oidc_auth.utils.permissions import flush_permission_cache

        flush_permission_cache()
        counter.reset()
        listed = self._filter(kind, rows)
        return counter.count, listed

    @pytest.mark.parametrize("kind", ["experiments", "registered_models"])
    def test_search_filter_statements_constant_in_rows(self, grants, counter, kind):
        from mlflow_oidc_auth.tests.search_paging_helpers import make_experiments, make_registered_models

        make = make_experiments if kind == "experiments" else make_registered_models
        key = "experiment_id" if kind == "experiments" else "name"
        ident = str if kind == "experiments" else "model-{}".format

        count_100, listed_100 = self._cold_count(counter, kind, make(100))
        report_100 = counter.report()
        count_500, listed_500 = self._cold_count(counter, kind, make(500))

        # The filter really filtered: exactly the rows granted directly or through a group.
        assert [row[key] for row in listed_100] == [ident(i) for i in range(0, 100, 10)]
        assert [row[key] for row in listed_500] == [ident(i) for i in range(0, 500, 10)]
        assert count_100 == count_500, f"{count_100} statements for 100 rows, {count_500} for 500\n{report_100}\n{counter.report()}"
        assert 0 < count_500 <= 20, counter.report()


class TestSingleCheckCost:
    """A single-resource check must not read the user's whole grant set (issue #460 review).

    Accounts that create resources accumulate a direct grant per resource; a check of one of them
    looks its grants up by index, as before the grant context, so its cost does not grow with them.
    """

    def _count_one_check(self, counter, monkeypatch, username, experiment_id):
        from types import SimpleNamespace

        from mlflow_oidc_auth.utils import permissions

        tracking = SimpleNamespace(get_experiment=lambda experiment_id: SimpleNamespace(name=f"exp-{experiment_id}"))
        monkeypatch.setattr(permissions, "_get_tracking_store", lambda: tracking)
        permissions.flush_permission_cache()
        counter.reset()
        result = permissions.resolve_permission("experiment", experiment_id, username)
        return counter.count, result

    @pytest.mark.parametrize("experiment_id, granted", [("5", True), ("no-grant", False)])
    def test_single_check_statements_do_not_grow_with_direct_grants(self, store, counter, monkeypatch, experiment_id, granted):
        import mlflow_oidc_auth.store as store_mod
        from mlflow_oidc_auth.config import config

        monkeypatch.setattr(store_mod, "store", store)
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
        counts = {}
        for n_grants in (10, 1000):
            username = f"creator{n_grants}@example.com"
            store.create_user(username, username)
            for i in range(n_grants):
                store.create_experiment_permission(str(i), username, "MANAGE")
            counts[n_grants], result = self._count_one_check(counter, monkeypatch, username, experiment_id)
            assert result.permission.can_manage is granted
        assert counts[10] == counts[1000], f"a single check scales with the user's grants: {counts}"
        # Found directly: one indexed lookup. Not found: the two direct lookups, the group ids and
        # the user's pattern list (no groups, so no group pattern list).
        assert counts[1000] == (1 if granted else 4), counter.report()


def _gateway_item(key):
    return lambda i: {key: f"gw-{i}"}


class TestGatewayManageableFilterStatements:
    """The gateway 'manageable' filters resolve every row against one bulk context (issue #460 review)."""

    @pytest.mark.parametrize(
        "filter_name, grant, item",
        [
            ("filter_manageable_gateway_endpoints", "create_gateway_endpoint_permission", _gateway_item("name")),
            ("filter_manageable_gateway_secrets", "create_gateway_secret_permission", _gateway_item("secret_name")),
            ("filter_manageable_gateway_model_definitions", "create_gateway_model_definition_permission", _gateway_item("name")),
        ],
    )
    def test_gateway_filter_statements_constant_in_rows(self, store, counter, monkeypatch, filter_name, grant, item):
        import mlflow_oidc_auth.store as store_mod
        import mlflow_oidc_auth.utils.batch_permissions as bp
        from mlflow_oidc_auth.config import config
        from mlflow_oidc_auth.utils.permissions import flush_permission_cache

        monkeypatch.setattr(store_mod, "store", store)
        monkeypatch.setattr(config, "MLFLOW_ENABLE_WORKSPACES", False)
        monkeypatch.setattr(config, "DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
        store.create_user("gw@example.com", "Gateway user")
        for i in range(0, 200, 10):
            getattr(store, grant)(f"gw-{i}", "gw@example.com", "MANAGE")

        counts = {}
        for n in (50, 200):
            flush_permission_cache()
            counter.reset()
            manageable = getattr(bp, filter_name)("gw@example.com", [item(i) for i in range(n)])
            counts[n] = counter.count
            assert len(manageable) == n // 10
        assert counts[50] == counts[200], f"statements scale with rows: {counts}"
        assert counts[200] <= 6, counter.report()
