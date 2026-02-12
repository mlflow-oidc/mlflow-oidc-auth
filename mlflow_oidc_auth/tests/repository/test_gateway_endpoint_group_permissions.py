"""Tests for gateway group-level permission repositories (endpoint, secret, model definition)."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.gateway_endpoint_group_permissions import GatewayEndpointGroupPermissionRepository
from mlflow_oidc_auth.repository.gateway_secret_group_permissions import GatewaySecretGroupPermissionRepository
from mlflow_oidc_auth.repository.gateway_model_definition_group_permissions import GatewayModelDefinitionGroupPermissionRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    """Create a mock session with context-manager support."""
    s = MagicMock()
    s.__enter__.return_value = s
    s.__exit__.return_value = None
    return s


@pytest.fixture
def session_maker(session):
    """Create a mock session maker."""
    return MagicMock(return_value=session)


# ---------------------------------------------------------------------------
# Parameterised definitions for each resource type
# ---------------------------------------------------------------------------

RESOURCE_CONFIGS = [
    pytest.param(
        GatewayEndpointGroupPermissionRepository,
        "mlflow_oidc_auth.repository.gateway_endpoint_group_permissions",
        "endpoint_id",
        "SqlGatewayEndpointGroupPermission",
        "list_groups_for_endpoint",
        id="endpoint",
    ),
    pytest.param(
        GatewaySecretGroupPermissionRepository,
        "mlflow_oidc_auth.repository.gateway_secret_group_permissions",
        "secret_id",
        "SqlGatewaySecretGroupPermission",
        "list_groups_for_secret",
        id="secret",
    ),
    pytest.param(
        GatewayModelDefinitionGroupPermissionRepository,
        "mlflow_oidc_auth.repository.gateway_model_definition_group_permissions",
        "model_definition_id",
        "SqlGatewayModelDefinitionGroupPermission",
        "list_groups_for_model_definition",
        id="model_definition",
    ),
]


# ---------------------------------------------------------------------------
# Tests — _get_group_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,field,sql_cls,list_groups_method", RESOURCE_CONFIGS)
class TestGetGroupPermission:
    """Tests for _get_group_permission private helper."""

    def test_found(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test successful lookup returns the row."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        session.query().join().filter().one.return_value = perm
        result = repo._get_group_permission(session, "res-1", "devs")
        assert result == perm

    def test_not_found(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test NoResultFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().join().filter().one.side_effect = NoResultFound()
        with pytest.raises(MlflowException) as exc:
            repo._get_group_permission(session, "res-1", "devs")
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"

    def test_multiple_found(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test MultipleResultsFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().join().filter().one.side_effect = MultipleResultsFound()
        with pytest.raises(MlflowException) as exc:
            repo._get_group_permission(session, "res-1", "devs")
        assert exc.value.error_code == "INVALID_STATE"


# ---------------------------------------------------------------------------
# Tests — grant_group_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,field,sql_cls,list_groups_method", RESOURCE_CONFIGS)
class TestGrantGroupPermission:
    """Tests for grant_group_permission."""

    def test_success(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test successful grant returns the entity."""
        repo = repo_cls(session_maker)
        group = MagicMock(id=10)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{mod}.get_group", return_value=group),
            patch(f"{mod}.{sql_cls}", return_value=perm),
            patch(f"{mod}._validate_permission"),
        ):
            result = repo.grant_group_permission("devs", "res-1", "READ")
        assert result == "entity"
        session.add.assert_called_once_with(perm)
        session.flush.assert_called_once()

    def test_integrity_error(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test IntegrityError raises RESOURCE_ALREADY_EXISTS."""
        repo = repo_cls(session_maker)
        group = MagicMock(id=10)
        session.flush.side_effect = IntegrityError("stmt", "params", "orig")
        with (
            patch(f"{mod}.get_group", return_value=group),
            patch(f"{mod}.{sql_cls}", return_value=MagicMock()),
            patch(f"{mod}._validate_permission"),
        ):
            with pytest.raises(MlflowException) as exc:
                repo.grant_group_permission("devs", "res-1", "READ")
        assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


# ---------------------------------------------------------------------------
# Tests — get_group_permission_for_user
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,field,sql_cls,list_groups_method", RESOURCE_CONFIGS)
class TestGetGroupPermissionForUser:
    """Tests for get_group_permission_for_user."""

    def test_success(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test successful get returns the entity."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with patch.object(repo, "_get_group_permission", return_value=perm):
            assert repo.get_group_permission_for_user("res-1", "devs") == "entity"


# ---------------------------------------------------------------------------
# Tests — list_permissions_for_group
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,field,sql_cls,list_groups_method", RESOURCE_CONFIGS)
class TestListPermissionsForGroup:
    """Tests for list_permissions_for_group."""

    def test_returns_entities(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test list returns mapped entities."""
        repo = repo_cls(session_maker)
        group = MagicMock(id=10)
        perm1 = MagicMock()
        perm1.to_mlflow_entity.return_value = "e1"
        perm2 = MagicMock()
        perm2.to_mlflow_entity.return_value = "e2"
        session.query().filter().all.return_value = [perm1, perm2]
        with patch(f"{mod}.get_group", return_value=group):
            result = repo.list_permissions_for_group("devs")
        assert result == ["e1", "e2"]

    def test_empty(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test list returns empty list when no permissions exist."""
        repo = repo_cls(session_maker)
        group = MagicMock(id=10)
        session.query().filter().all.return_value = []
        with patch(f"{mod}.get_group", return_value=group):
            assert repo.list_permissions_for_group("devs") == []


# ---------------------------------------------------------------------------
# Tests — update_group_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,field,sql_cls,list_groups_method", RESOURCE_CONFIGS)
class TestUpdateGroupPermission:
    """Tests for update_group_permission."""

    def test_success(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test successful update sets permission and flushes."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch.object(repo, "_get_group_permission", return_value=perm),
            patch(f"{mod}._validate_permission"),
        ):
            result = repo.update_group_permission("devs", "res-1", "EDIT")
        assert result == "entity"
        assert perm.permission == "EDIT"
        session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — revoke_group_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,field,sql_cls,list_groups_method", RESOURCE_CONFIGS)
class TestRevokeGroupPermission:
    """Tests for revoke_group_permission."""

    def test_success(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test successful revoke deletes and flushes."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        with patch.object(repo, "_get_group_permission", return_value=perm):
            repo.revoke_group_permission("devs", "res-1")
        session.delete.assert_called_once_with(perm)
        session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — list_groups_for_*  (extra method unique to group repos)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,field,sql_cls,list_groups_method", RESOURCE_CONFIGS)
class TestListGroupsForResource:
    """Tests for the list_groups_for_<resource> method."""

    def test_returns_tuples(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test that list_groups_for_* returns (group_name, permission) tuples."""
        repo = repo_cls(session_maker)
        perm1 = MagicMock(permission="READ")
        perm2 = MagicMock(permission="MANAGE")
        session.query().join().filter().all.return_value = [(perm1, "group-a"), (perm2, "group-b")]
        method = getattr(repo, list_groups_method)
        result = method("res-1")
        assert result == [("group-a", "READ"), ("group-b", "MANAGE")]

    def test_empty(self, session_maker, session, repo_cls, mod, field, sql_cls, list_groups_method):
        """Test empty result set."""
        repo = repo_cls(session_maker)
        session.query().join().filter().all.return_value = []
        method = getattr(repo, list_groups_method)
        assert method("res-1") == []
