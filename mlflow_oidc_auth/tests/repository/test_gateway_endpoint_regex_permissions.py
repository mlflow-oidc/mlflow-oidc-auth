"""Tests for gateway user-level regex permission repositories (endpoint, secret, model definition)."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.gateway_endpoint_regex_permissions import (
    GatewayEndpointPermissionRegexRepository,
)
from mlflow_oidc_auth.repository.gateway_secret_regex_permissions import (
    GatewaySecretPermissionRegexRepository,
)
from mlflow_oidc_auth.repository.gateway_model_definition_regex_permissions import (
    GatewayModelDefinitionPermissionRegexRepository,
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
        GatewayEndpointPermissionRegexRepository,
        "mlflow_oidc_auth.repository.gateway_endpoint_regex_permissions",
        id="endpoint",
    ),
    pytest.param(
        GatewaySecretPermissionRegexRepository,
        "mlflow_oidc_auth.repository.gateway_secret_regex_permissions",
        id="secret",
    ),
    pytest.param(
        GatewayModelDefinitionPermissionRegexRepository,
        "mlflow_oidc_auth.repository.gateway_model_definition_regex_permissions",
        id="model_definition",
    ),
]


# ---------------------------------------------------------------------------
# Tests — _get_regex_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod", RESOURCE_CONFIGS)
class TestGetRegexPermission:
    """Tests for the _get_regex_permission helper (inherited from base)."""

    def test_found(self, session_maker, session, repo_cls, mod):
        """Test successful lookup returns the row."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        session.query().filter().one.return_value = perm
        assert repo._get_regex_permission(session, 1, 42) == perm

    def test_not_found(self, session_maker, session, repo_cls, mod):
        """Test NoResultFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().filter().one.side_effect = NoResultFound()
        with pytest.raises(MlflowException) as exc:
            repo._get_regex_permission(session, 1, 42)
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"

    def test_multiple_found(self, session_maker, session, repo_cls, mod):
        """Test MultipleResultsFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().filter().one.side_effect = MultipleResultsFound()
        with pytest.raises(MlflowException) as exc:
            repo._get_regex_permission(session, 1, 42)
        assert exc.value.error_code == "INVALID_STATE"


# ---------------------------------------------------------------------------
# Tests — grant (delegated to base)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod", RESOURCE_CONFIGS)
class TestGrant:
    """Tests for grant."""

    def test_success(self, session_maker, session, repo_cls, mod):
        """Test successful grant returns the entity."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{_BASE}.get_user", return_value=user),
            patch.object(type(repo), "model_class", return_value=perm),
            patch(f"{_BASE}._validate_permission"),
            patch(f"{_BASE}.validate_regex"),
        ):
            result = repo.grant("regex-.*", 1, "READ", "alice")
        assert result == "entity"
        session.add.assert_called_once_with(perm)
        session.flush.assert_called_once()

    def test_integrity_error(self, session_maker, session, repo_cls, mod):
        """Test IntegrityError raises RESOURCE_ALREADY_EXISTS."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        session.flush.side_effect = IntegrityError("stmt", "params", "orig")
        with (
            patch(f"{_BASE}.get_user", return_value=user),
            patch.object(type(repo), "model_class", return_value=MagicMock()),
            patch(f"{_BASE}._validate_permission"),
            patch(f"{_BASE}.validate_regex"),
        ):
            with pytest.raises(MlflowException) as exc:
                repo.grant("regex-.*", 1, "READ", "alice")
        assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


# ---------------------------------------------------------------------------
# Tests — get (overridden in subclass, uses local imports)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod", RESOURCE_CONFIGS)
class TestGet:
    """Tests for get."""

    def test_success(self, session_maker, session, repo_cls, mod):
        """Test get delegates to private getter and returns entity."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{mod}.get_user", return_value=user),
            patch.object(repo, "_get_regex_permission", return_value=perm),
        ):
            assert repo.get(1, "alice") == "entity"


# ---------------------------------------------------------------------------
# Tests — list_regex_for_user (delegated to base)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod", RESOURCE_CONFIGS)
class TestListRegexForUser:
    """Tests for list_regex_for_user."""

    def test_returns_entities(self, session_maker, session, repo_cls, mod):
        """Test list returns mapped entities ordered by priority."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm1 = MagicMock()
        perm1.to_mlflow_entity.return_value = "e1"
        perm2 = MagicMock()
        perm2.to_mlflow_entity.return_value = "e2"
        session.query().filter().order_by().all.return_value = [perm1, perm2]
        with patch(f"{_BASE}.get_user", return_value=user):
            result = repo.list_regex_for_user("alice")
        assert result == ["e1", "e2"]

    def test_empty(self, session_maker, session, repo_cls, mod):
        """Test empty list."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        session.query().filter().order_by().all.return_value = []
        with patch(f"{_BASE}.get_user", return_value=user):
            assert repo.list_regex_for_user("alice") == []


# ---------------------------------------------------------------------------
# Tests — update (overridden in subclass, uses local imports)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod", RESOURCE_CONFIGS)
class TestUpdate:
    """Tests for update."""

    def test_success(self, session_maker, session, repo_cls, mod):
        """Test successful update sets fields and commits."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{mod}.get_user", return_value=user),
            patch.object(repo, "_get_regex_permission", return_value=perm),
            patch(f"{mod}._validate_permission"),
            patch(f"{mod}.validate_regex"),
        ):
            result = repo.update(1, "new-.*", 5, "EDIT", "alice")
        assert result == "entity"
        assert perm.priority == 5
        assert perm.permission == "EDIT"
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — revoke (overridden in subclass, uses local imports)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod", RESOURCE_CONFIGS)
class TestRevoke:
    """Tests for revoke."""

    def test_success(self, session_maker, session, repo_cls, mod):
        """Test successful revoke deletes and commits."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm = MagicMock()
        with (
            patch(f"{mod}.get_user", return_value=user),
            patch.object(repo, "_get_regex_permission", return_value=perm),
        ):
            assert repo.revoke(1, "alice") is None
        session.delete.assert_called_once_with(perm)
        session.commit.assert_called_once()
