"""Tests for gateway user-level regex permission repositories (endpoint, secret, model definition)."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.gateway_endpoint_regex_permissions import GatewayEndpointPermissionRegexRepository
from mlflow_oidc_auth.repository.gateway_secret_regex_permissions import GatewaySecretPermissionRegexRepository
from mlflow_oidc_auth.repository.gateway_model_definition_regex_permissions import GatewayModelDefinitionPermissionRegexRepository


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

_PRIVATE_GETTER = {
    "endpoint": "_get_endpoint_regex_permission",
    "secret": "_get_secret_regex_permission",
    "model_definition": "_get_model_definition_regex_permission",
}

RESOURCE_CONFIGS = [
    pytest.param(
        GatewayEndpointPermissionRegexRepository,
        "mlflow_oidc_auth.repository.gateway_endpoint_regex_permissions",
        "_get_endpoint_regex_permission",
        "SqlGatewayEndpointRegexPermission",
        id="endpoint",
    ),
    pytest.param(
        GatewaySecretPermissionRegexRepository,
        "mlflow_oidc_auth.repository.gateway_secret_regex_permissions",
        "_get_secret_regex_permission",
        "SqlGatewaySecretRegexPermission",
        id="secret",
    ),
    pytest.param(
        GatewayModelDefinitionPermissionRegexRepository,
        "mlflow_oidc_auth.repository.gateway_model_definition_regex_permissions",
        "_get_model_def_regex_permission",
        "SqlGatewayModelDefinitionRegexPermission",
        id="model_definition",
    ),
]


# ---------------------------------------------------------------------------
# Tests — _get_*_regex_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestGetRegexPermission:
    """Tests for the private _get_*_regex_permission helper."""

    def test_found(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test successful lookup returns the row."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        session.query().filter().one.return_value = perm
        fn = getattr(repo, getter)
        assert fn(session, 1, 42) == perm

    def test_not_found(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test NoResultFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().filter().one.side_effect = NoResultFound()
        fn = getattr(repo, getter)
        with pytest.raises(MlflowException) as exc:
            fn(session, 1, 42)
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"

    def test_multiple_found(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test MultipleResultsFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().filter().one.side_effect = MultipleResultsFound()
        fn = getattr(repo, getter)
        with pytest.raises(MlflowException) as exc:
            fn(session, 1, 42)
        assert exc.value.error_code == "INVALID_STATE"


# ---------------------------------------------------------------------------
# Tests — grant
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestGrant:
    """Tests for grant."""

    def test_success(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test successful grant returns the entity."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{mod}.get_user", return_value=user),
            patch(f"{mod}.{sql_cls}", return_value=perm),
            patch(f"{mod}._validate_permission"),
            patch(f"{mod}.validate_regex"),
        ):
            result = repo.grant("regex-.*", 1, "READ", "alice")
        assert result == "entity"
        session.add.assert_called_once_with(perm)
        session.flush.assert_called_once()

    def test_integrity_error(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test IntegrityError raises RESOURCE_ALREADY_EXISTS."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        session.flush.side_effect = IntegrityError("stmt", "params", "orig")
        with (
            patch(f"{mod}.get_user", return_value=user),
            patch(f"{mod}.{sql_cls}", return_value=MagicMock()),
            patch(f"{mod}._validate_permission"),
            patch(f"{mod}.validate_regex"),
        ):
            with pytest.raises(MlflowException) as exc:
                repo.grant("regex-.*", 1, "READ", "alice")
        assert exc.value.error_code == "RESOURCE_ALREADY_EXISTS"


# ---------------------------------------------------------------------------
# Tests — get
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestGet:
    """Tests for get."""

    def test_success(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test get delegates to private getter and returns entity."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{mod}.get_user", return_value=user),
            patch.object(repo, getter, return_value=perm),
        ):
            assert repo.get(1, "alice") == "entity"


# ---------------------------------------------------------------------------
# Tests — list_regex_for_user
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestListRegexForUser:
    """Tests for list_regex_for_user."""

    def test_returns_entities(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test list returns mapped entities ordered by priority."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm1 = MagicMock()
        perm1.to_mlflow_entity.return_value = "e1"
        perm2 = MagicMock()
        perm2.to_mlflow_entity.return_value = "e2"
        session.query().filter().order_by().all.return_value = [perm1, perm2]
        with patch(f"{mod}.get_user", return_value=user):
            result = repo.list_regex_for_user("alice")
        assert result == ["e1", "e2"]

    def test_empty(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test empty list."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        session.query().filter().order_by().all.return_value = []
        with patch(f"{mod}.get_user", return_value=user):
            assert repo.list_regex_for_user("alice") == []


# ---------------------------------------------------------------------------
# Tests — update
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestUpdate:
    """Tests for update."""

    def test_success(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test successful update sets fields and commits."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{mod}.get_user", return_value=user),
            patch.object(repo, getter, return_value=perm),
            patch(f"{mod}._validate_permission"),
            patch(f"{mod}.validate_regex"),
        ):
            result = repo.update(1, "new-.*", 5, "EDIT", "alice")
        assert result == "entity"
        assert perm.priority == 5
        assert perm.permission == "EDIT"
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — revoke
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestRevoke:
    """Tests for revoke."""

    def test_success(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test successful revoke deletes and commits."""
        repo = repo_cls(session_maker)
        user = MagicMock(id=42)
        perm = MagicMock()
        with (
            patch(f"{mod}.get_user", return_value=user),
            patch.object(repo, getter, return_value=perm),
        ):
            assert repo.revoke(1, "alice") is None
        session.delete.assert_called_once_with(perm)
        session.commit.assert_called_once()
