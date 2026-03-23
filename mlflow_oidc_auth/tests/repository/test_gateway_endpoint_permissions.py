"""Tests for gateway user-level permission repositories (endpoint, secret, model definition)."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.gateway_endpoint_permissions import (
    GatewayEndpointPermissionRepository,
)
from mlflow_oidc_auth.repository.gateway_secret_permissions import (
    GatewaySecretPermissionRepository,
)
from mlflow_oidc_auth.repository.gateway_model_definition_permissions import (
    GatewayModelDefinitionPermissionRepository,
)

_BASE = "mlflow_oidc_auth.repository._base"

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
        GatewayEndpointPermissionRepository,
        "endpoint_id",
        id="endpoint",
    ),
    pytest.param(
        GatewaySecretPermissionRepository,
        "secret_id",
        id="secret",
    ),
    pytest.param(
        GatewayModelDefinitionPermissionRepository,
        "model_definition_id",
        id="model_definition",
    ),
]


# ---------------------------------------------------------------------------
# Tests — _get_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,field", RESOURCE_CONFIGS)
class TestGetPermission:
    """Tests for _get_permission private helper."""

    def test_found(self, session_maker, session, repo_cls, field):
        """Test successful lookup returns the row."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        session.query().join().filter().one.return_value = perm
        result = repo._get_permission(session, "res-1", "alice")
        assert result == perm

    def test_not_found(self, session_maker, session, repo_cls, field):
        """Test NoResultFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().join().filter().one.side_effect = NoResultFound()
        with pytest.raises(MlflowException) as exc:
            repo._get_permission(session, "res-1", "alice")
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"

    def test_multiple_found(self, session_maker, session, repo_cls, field):
        """Test MultipleResultsFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().join().filter().one.side_effect = MultipleResultsFound()
        with pytest.raises(MlflowException) as exc:
            repo._get_permission(session, "res-1", "alice")
        assert exc.value.error_code == "INVALID_STATE"


# ---------------------------------------------------------------------------
# Tests — grant_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,field", RESOURCE_CONFIGS)
class TestGrantPermission:
    """Tests for grant_permission."""

    def test_success(self, session_maker, session, repo_cls, field):
        """Test successful grant returns the entity."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{_BASE}.get_user", return_value=user),
            patch.object(type(repo), "model_class", return_value=perm),
            patch(f"{_BASE}._validate_permission"),
        ):
            result = repo.grant_permission("res-1", "alice", "READ")
        assert result == "entity"
        session.add.assert_called_once_with(perm)
        session.flush.assert_called_once()

    def test_integrity_error(self, session_maker, session, repo_cls, field):
        """Test IntegrityError raises RESOURCE_ALREADY_EXISTS."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        session.flush.side_effect = IntegrityError("stmt", "params", "orig")
        with (
            patch(f"{_BASE}.get_user", return_value=user),
            patch.object(type(repo), "model_class", return_value=MagicMock()),
            patch(f"{_BASE}._validate_permission"),
        ):
            with pytest.raises(MlflowException) as exc:
                repo.grant_permission("res-1", "alice", "READ")
        assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


# ---------------------------------------------------------------------------
# Tests — get_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,field", RESOURCE_CONFIGS)
class TestGetPermissionPublic:
    """Tests for get_permission."""

    def test_success(self, session_maker, session, repo_cls, field):
        """Test get_permission delegates to _get_permission and returns entity."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with patch.object(repo, "_get_permission", return_value=perm):
            assert repo.get_permission("res-1", "alice") == "entity"


# ---------------------------------------------------------------------------
# Tests — list_permissions_for_user
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,field", RESOURCE_CONFIGS)
class TestListPermissionsForUser:
    """Tests for list_permissions_for_user."""

    def test_returns_entities(self, session_maker, session, repo_cls, field):
        """Test list returns mapped entities."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm1 = MagicMock()
        perm1.to_mlflow_entity.return_value = "e1"
        perm2 = MagicMock()
        perm2.to_mlflow_entity.return_value = "e2"
        session.query().filter().all.return_value = [perm1, perm2]
        with patch(f"{_BASE}.get_user", return_value=user):
            result = repo.list_permissions_for_user("alice")
        assert result == ["e1", "e2"]

    def test_empty(self, session_maker, session, repo_cls, field):
        """Test list returns empty list when no permissions exist."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        session.query().filter().all.return_value = []
        with patch(f"{_BASE}.get_user", return_value=user):
            assert repo.list_permissions_for_user("alice") == []


# ---------------------------------------------------------------------------
# Tests — update_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,field", RESOURCE_CONFIGS)
class TestUpdatePermission:
    """Tests for update_permission."""

    def test_success(self, session_maker, session, repo_cls, field):
        """Test successful update sets permission and flushes."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch.object(repo, "_get_permission", return_value=perm),
            patch(f"{_BASE}._validate_permission"),
        ):
            result = repo.update_permission("res-1", "alice", "EDIT")
        assert result == "entity"
        assert perm.permission == "EDIT"
        session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — revoke_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,field", RESOURCE_CONFIGS)
class TestRevokePermission:
    """Tests for revoke_permission."""

    def test_success(self, session_maker, session, repo_cls, field):
        """Test successful revoke deletes and flushes."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        with patch.object(repo, "_get_permission", return_value=perm):
            assert repo.revoke_permission("res-1", "alice") is None
        session.delete.assert_called_once_with(perm)
        session.flush.assert_called_once()
