"""Tests for gateway-related methods in sqlalchemy_store.py.

Covers the delegation from SqlAlchemyStore gateway methods
to the underlying repository classes.
"""

from unittest.mock import MagicMock

import pytest

from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore


def _one_session(store: SqlAlchemyStore) -> MagicMock:
    """Give ``store`` a session maker yielding one mock session, and return that session."""
    session = MagicMock()
    store.ManagedSessionMaker = MagicMock()
    store.ManagedSessionMaker.return_value.__enter__.return_value = session
    return session


@pytest.fixture
def store_with_mocked_repos() -> SqlAlchemyStore:
    """Create a SqlAlchemyStore with all gateway repositories mocked out."""
    s = object.__new__(SqlAlchemyStore)

    # Direct permission repos
    s.gateway_endpoint_repo = MagicMock()
    s.gateway_secret_repo = MagicMock()
    s.gateway_model_definition_repo = MagicMock()

    # Group permission repos
    s.gateway_endpoint_group_repo = MagicMock()
    s.gateway_secret_group_repo = MagicMock()
    s.gateway_model_definition_group_repo = MagicMock()

    # Regex permission repos
    s.gateway_endpoint_regex_repo = MagicMock()
    s.gateway_secret_regex_repo = MagicMock()
    s.gateway_model_definition_regex_repo = MagicMock()

    # Group regex permission repos
    s.gateway_endpoint_group_regex_repo = MagicMock()
    s.gateway_secret_group_regex_repo = MagicMock()
    s.gateway_model_definition_group_regex_repo = MagicMock()

    return s


# ---------------------------------------------------------------------------
# Gateway Endpoint Permissions
# ---------------------------------------------------------------------------


class TestGatewayEndpointPermissions:
    """Tests for gateway endpoint permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_gateway_endpoint_permission("ep-1", "alice", "READ")
        store_with_mocked_repos.gateway_endpoint_repo.grant_permission.assert_called_once_with("ep-1", "alice", "READ")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_gateway_endpoint_permission("ep-1", "alice")
        store_with_mocked_repos.gateway_endpoint_repo.get_permission.assert_called_once_with("ep-1", "alice")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_gateway_endpoint_permissions("alice")
        store_with_mocked_repos.gateway_endpoint_repo.list_permissions_for_user.assert_called_once_with("alice")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_gateway_endpoint_permission("ep-1", "alice", "MANAGE")
        store_with_mocked_repos.gateway_endpoint_repo.update_permission.assert_called_once_with("ep-1", "alice", "MANAGE")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_gateway_endpoint_permission("ep-1", "alice")
        store_with_mocked_repos.gateway_endpoint_repo.revoke_permission.assert_called_once_with("ep-1", "alice")

    def test_rename(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        session = _one_session(store_with_mocked_repos)
        store_with_mocked_repos.rename_gateway_endpoint_permissions("old-ep", "new-ep")
        for repo in (store_with_mocked_repos.gateway_endpoint_repo, store_with_mocked_repos.gateway_endpoint_group_repo):
            repo._wipe_in.assert_called_once_with(session, "new-ep")
            repo._rename_in.assert_called_once_with(session, "old-ep", "new-ep")

    def test_rename_to_same_name_is_a_no_op(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.ManagedSessionMaker = MagicMock()
        store_with_mocked_repos.rename_gateway_endpoint_permissions("ep", "ep")
        store_with_mocked_repos.ManagedSessionMaker.assert_not_called()


# ---------------------------------------------------------------------------
# Gateway Secret Permissions
# ---------------------------------------------------------------------------


class TestGatewaySecretPermissions:
    """Tests for gateway secret permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_gateway_secret_permission("s-1", "alice", "READ")
        store_with_mocked_repos.gateway_secret_repo.grant_permission.assert_called_once_with("s-1", "alice", "READ")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_gateway_secret_permission("s-1", "alice")
        store_with_mocked_repos.gateway_secret_repo.get_permission.assert_called_once_with("s-1", "alice")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_gateway_secret_permissions("alice")
        store_with_mocked_repos.gateway_secret_repo.list_permissions_for_user.assert_called_once_with("alice")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_gateway_secret_permission("s-1", "alice", "MANAGE")
        store_with_mocked_repos.gateway_secret_repo.update_permission.assert_called_once_with("s-1", "alice", "MANAGE")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_gateway_secret_permission("s-1", "alice")
        store_with_mocked_repos.gateway_secret_repo.revoke_permission.assert_called_once_with("s-1", "alice")


# ---------------------------------------------------------------------------
# Gateway Model Definition Permissions
# ---------------------------------------------------------------------------


class TestGatewayModelDefinitionPermissions:
    """Tests for gateway model definition permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_gateway_model_definition_permission("m-1", "alice", "READ")
        store_with_mocked_repos.gateway_model_definition_repo.grant_permission.assert_called_once_with("m-1", "alice", "READ")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_gateway_model_definition_permission("m-1", "alice")
        store_with_mocked_repos.gateway_model_definition_repo.get_permission.assert_called_once_with("m-1", "alice")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_gateway_model_definition_permissions("alice")
        store_with_mocked_repos.gateway_model_definition_repo.list_permissions_for_user.assert_called_once_with("alice")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_gateway_model_definition_permission("m-1", "alice", "EDIT")
        store_with_mocked_repos.gateway_model_definition_repo.update_permission.assert_called_once_with("m-1", "alice", "EDIT")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_gateway_model_definition_permission("m-1", "alice")
        store_with_mocked_repos.gateway_model_definition_repo.revoke_permission.assert_called_once_with("m-1", "alice")

    def test_rename_model_definition_to_same_name_is_a_no_op(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.ManagedSessionMaker = MagicMock()
        store_with_mocked_repos.rename_gateway_model_definition_permissions("m", "m")
        store_with_mocked_repos.ManagedSessionMaker.assert_not_called()

    def test_rename_gateway_model_definition_permissions(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        session = _one_session(store_with_mocked_repos)
        store_with_mocked_repos.rename_gateway_model_definition_permissions("old-m", "new-m")
        for repo in (store_with_mocked_repos.gateway_model_definition_repo, store_with_mocked_repos.gateway_model_definition_group_repo):
            repo._wipe_in.assert_called_once_with(session, "new-m")
            repo._rename_in.assert_called_once_with(session, "old-m", "new-m")

    def test_rename_moves_only_the_recorded_rows(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        session = _one_session(store_with_mocked_repos)
        store_with_mocked_repos.rename_gateway_model_definition_permissions("old-m", "new-m", [[[1, 7, "READ"]], [[2, 9, "EDIT"]]])
        store_with_mocked_repos.gateway_model_definition_repo._rename_ids_in.assert_called_once_with(session, [[1, 7, "READ"]], "old-m", "new-m")
        store_with_mocked_repos.gateway_model_definition_group_repo._rename_ids_in.assert_called_once_with(session, [[2, 9, "EDIT"]], "old-m", "new-m")
        store_with_mocked_repos.gateway_model_definition_repo._rename_in.assert_not_called()

    def test_wipe_runs_in_one_session(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        session = _one_session(store_with_mocked_repos)
        store_with_mocked_repos.wipe_gateway_model_definition_permissions("m-1")
        store_with_mocked_repos.gateway_model_definition_repo._wipe_in.assert_called_once_with(session, "m-1")
        store_with_mocked_repos.gateway_model_definition_group_repo._wipe_in.assert_called_once_with(session, "m-1")

    def test_grant_creator_clears_the_name_and_grants_manage_in_one_session(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        session = _one_session(store_with_mocked_repos)
        store_with_mocked_repos.grant_creator_gateway_model_definition_permission("m-1", "alice")
        store_with_mocked_repos.gateway_model_definition_repo._wipe_in.assert_called_once_with(session, "m-1")
        store_with_mocked_repos.gateway_model_definition_group_repo._wipe_in.assert_called_once_with(session, "m-1")
        store_with_mocked_repos.gateway_model_definition_repo._grant_in.assert_called_once_with(session, "m-1", "alice", "MANAGE")


# ---------------------------------------------------------------------------
# Gateway Endpoint Group Permissions
# ---------------------------------------------------------------------------


class TestGatewayEndpointGroupPermissions:
    """Tests for gateway endpoint group permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_group_gateway_endpoint_permission("devs", "ep-1", "READ")
        store_with_mocked_repos.gateway_endpoint_group_repo.grant_group_permission.assert_called_once_with("devs", "ep-1", "READ")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_group_gateway_endpoint_permissions("devs")
        store_with_mocked_repos.gateway_endpoint_group_repo.list_permissions_for_group.assert_called_once_with("devs")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_user_groups_gateway_endpoint_permission("ep-1", "devs")
        store_with_mocked_repos.gateway_endpoint_group_repo.get_group_permission_for_user.assert_called_once_with("ep-1", "devs")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_group_gateway_endpoint_permission("devs", "ep-1", "MANAGE")
        store_with_mocked_repos.gateway_endpoint_group_repo.update_group_permission.assert_called_once_with("devs", "ep-1", "MANAGE")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_group_gateway_endpoint_permission("devs", "ep-1")
        store_with_mocked_repos.gateway_endpoint_group_repo.revoke_group_permission.assert_called_once_with("devs", "ep-1")


# ---------------------------------------------------------------------------
# Gateway Secret Group Permissions
# ---------------------------------------------------------------------------


class TestGatewaySecretGroupPermissions:
    """Tests for gateway secret group permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_group_gateway_secret_permission("devs", "s-1", "READ")
        store_with_mocked_repos.gateway_secret_group_repo.grant_group_permission.assert_called_once_with("devs", "s-1", "READ")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_group_gateway_secret_permissions("devs")
        store_with_mocked_repos.gateway_secret_group_repo.list_permissions_for_group.assert_called_once_with("devs")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_user_groups_gateway_secret_permission("s-1", "devs")
        store_with_mocked_repos.gateway_secret_group_repo.get_group_permission_for_user.assert_called_once_with("s-1", "devs")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_group_gateway_secret_permission("devs", "s-1", "MANAGE")
        store_with_mocked_repos.gateway_secret_group_repo.update_group_permission.assert_called_once_with("devs", "s-1", "MANAGE")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_group_gateway_secret_permission("devs", "s-1")
        store_with_mocked_repos.gateway_secret_group_repo.revoke_group_permission.assert_called_once_with("devs", "s-1")


# ---------------------------------------------------------------------------
# Gateway Model Definition Group Permissions
# ---------------------------------------------------------------------------


class TestGatewayModelDefinitionGroupPermissions:
    """Tests for gateway model definition group permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_group_gateway_model_definition_permission("devs", "m-1", "READ")
        store_with_mocked_repos.gateway_model_definition_group_repo.grant_group_permission.assert_called_once_with("devs", "m-1", "READ")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_group_gateway_model_definition_permissions("devs")
        store_with_mocked_repos.gateway_model_definition_group_repo.list_permissions_for_group.assert_called_once_with("devs")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_user_groups_gateway_model_definition_permission("m-1", "devs")
        store_with_mocked_repos.gateway_model_definition_group_repo.get_group_permission_for_user.assert_called_once_with("m-1", "devs")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_group_gateway_model_definition_permission("devs", "m-1", "EDIT")
        store_with_mocked_repos.gateway_model_definition_group_repo.update_group_permission.assert_called_once_with("devs", "m-1", "EDIT")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_group_gateway_model_definition_permission("devs", "m-1")
        store_with_mocked_repos.gateway_model_definition_group_repo.revoke_group_permission.assert_called_once_with("devs", "m-1")


# ---------------------------------------------------------------------------
# Gateway Endpoint Regex Permissions
# ---------------------------------------------------------------------------


class TestGatewayEndpointRegexPermissions:
    """Tests for gateway endpoint regex permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_gateway_endpoint_regex_permission("^ep-.*", 5, "READ", "alice")
        store_with_mocked_repos.gateway_endpoint_regex_repo.grant.assert_called_once_with("^ep-.*", 5, "READ", "alice")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_gateway_endpoint_regex_permission(1, "alice")
        store_with_mocked_repos.gateway_endpoint_regex_repo.get.assert_called_once_with(1, "alice")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_gateway_endpoint_regex_permissions("alice")
        store_with_mocked_repos.gateway_endpoint_regex_repo.list_regex_for_user.assert_called_once_with("alice")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_gateway_endpoint_regex_permission(1, "^new-.*", 10, "MANAGE", "alice")
        store_with_mocked_repos.gateway_endpoint_regex_repo.update.assert_called_once_with(1, "^new-.*", 10, "MANAGE", "alice")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_gateway_endpoint_regex_permission(1, "alice")
        store_with_mocked_repos.gateway_endpoint_regex_repo.revoke.assert_called_once_with(1, "alice")


# ---------------------------------------------------------------------------
# Gateway Secret Regex Permissions
# ---------------------------------------------------------------------------


class TestGatewaySecretRegexPermissions:
    """Tests for gateway secret regex permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_gateway_secret_regex_permission("^s-.*", 5, "READ", "alice")
        store_with_mocked_repos.gateway_secret_regex_repo.grant.assert_called_once_with("^s-.*", 5, "READ", "alice")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_gateway_secret_regex_permission(1, "alice")
        store_with_mocked_repos.gateway_secret_regex_repo.get.assert_called_once_with(1, "alice")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_gateway_secret_regex_permissions("alice")
        store_with_mocked_repos.gateway_secret_regex_repo.list_regex_for_user.assert_called_once_with("alice")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_gateway_secret_regex_permission(1, "^new-.*", 10, "MANAGE", "alice")
        store_with_mocked_repos.gateway_secret_regex_repo.update.assert_called_once_with(1, "^new-.*", 10, "MANAGE", "alice")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_gateway_secret_regex_permission(1, "alice")
        store_with_mocked_repos.gateway_secret_regex_repo.revoke.assert_called_once_with(1, "alice")


# ---------------------------------------------------------------------------
# Gateway Model Definition Regex Permissions
# ---------------------------------------------------------------------------


class TestGatewayModelDefinitionRegexPermissions:
    """Tests for gateway model definition regex permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_gateway_model_definition_regex_permission("^m-.*", 5, "READ", "alice")
        store_with_mocked_repos.gateway_model_definition_regex_repo.grant.assert_called_once_with("^m-.*", 5, "READ", "alice")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_gateway_model_definition_regex_permission(1, "alice")
        store_with_mocked_repos.gateway_model_definition_regex_repo.get.assert_called_once_with(1, "alice")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_gateway_model_definition_regex_permissions("alice")
        store_with_mocked_repos.gateway_model_definition_regex_repo.list_regex_for_user.assert_called_once_with("alice")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_gateway_model_definition_regex_permission(1, "^new-.*", 10, "MANAGE", "alice")
        store_with_mocked_repos.gateway_model_definition_regex_repo.update.assert_called_once_with(1, "^new-.*", 10, "MANAGE", "alice")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_gateway_model_definition_regex_permission(1, "alice")
        store_with_mocked_repos.gateway_model_definition_regex_repo.revoke.assert_called_once_with(1, "alice")


# ---------------------------------------------------------------------------
# Gateway Group Regex Permissions
# ---------------------------------------------------------------------------


class TestGatewayEndpointGroupRegexPermissions:
    """Tests for gateway endpoint group regex permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_group_gateway_endpoint_regex_permission("devs", "^ep-.*", 5, "READ")
        store_with_mocked_repos.gateway_endpoint_group_regex_repo.grant.assert_called_once_with("devs", "^ep-.*", 5, "READ")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_group_gateway_endpoint_regex_permission(1, "devs")
        store_with_mocked_repos.gateway_endpoint_group_regex_repo.get.assert_called_once_with(1, "devs")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_group_gateway_endpoint_regex_permissions("devs")
        store_with_mocked_repos.gateway_endpoint_group_regex_repo.list_permissions_for_group.assert_called_once_with("devs")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_group_gateway_endpoint_regex_permission(1, "devs", "^new-.*", 10, "MANAGE")
        store_with_mocked_repos.gateway_endpoint_group_regex_repo.update.assert_called_once_with(1, "devs", "^new-.*", 10, "MANAGE")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_group_gateway_endpoint_regex_permission(1, "devs")
        store_with_mocked_repos.gateway_endpoint_group_regex_repo.revoke.assert_called_once_with(1, "devs")


class TestGatewaySecretGroupRegexPermissions:
    """Tests for gateway secret group regex permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_group_gateway_secret_regex_permission("devs", "^s-.*", 5, "READ")
        store_with_mocked_repos.gateway_secret_group_regex_repo.grant.assert_called_once_with("devs", "^s-.*", 5, "READ")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_group_gateway_secret_regex_permission(1, "devs")
        store_with_mocked_repos.gateway_secret_group_regex_repo.get.assert_called_once_with(1, "devs")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_group_gateway_secret_regex_permissions("devs")
        store_with_mocked_repos.gateway_secret_group_regex_repo.list_permissions_for_group.assert_called_once_with("devs")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_group_gateway_secret_regex_permission(1, "devs", "^new-.*", 10, "MANAGE")
        store_with_mocked_repos.gateway_secret_group_regex_repo.update.assert_called_once_with(1, "devs", "^new-.*", 10, "MANAGE")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_group_gateway_secret_regex_permission(1, "devs")
        store_with_mocked_repos.gateway_secret_group_regex_repo.revoke.assert_called_once_with(1, "devs")


class TestGatewayModelDefinitionGroupRegexPermissions:
    """Tests for gateway model definition group regex permission store methods."""

    def test_create(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.create_group_gateway_model_definition_regex_permission("devs", "^m-.*", 5, "READ")
        store_with_mocked_repos.gateway_model_definition_group_regex_repo.grant.assert_called_once_with("devs", "^m-.*", 5, "READ")

    def test_get(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.get_group_gateway_model_definition_regex_permission(1, "devs")
        store_with_mocked_repos.gateway_model_definition_group_regex_repo.get.assert_called_once_with(1, "devs")

    def test_list(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.list_group_gateway_model_definition_regex_permissions("devs")
        store_with_mocked_repos.gateway_model_definition_group_regex_repo.list_permissions_for_group.assert_called_once_with("devs")

    def test_update(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.update_group_gateway_model_definition_regex_permission(1, "devs", "^new-.*", 10, "EDIT")
        store_with_mocked_repos.gateway_model_definition_group_regex_repo.update.assert_called_once_with(1, "devs", "^new-.*", 10, "EDIT")

    def test_delete(self, store_with_mocked_repos: SqlAlchemyStore) -> None:
        store_with_mocked_repos.delete_group_gateway_model_definition_regex_permission(1, "devs")
        store_with_mocked_repos.gateway_model_definition_group_regex_repo.revoke.assert_called_once_with(1, "devs")
