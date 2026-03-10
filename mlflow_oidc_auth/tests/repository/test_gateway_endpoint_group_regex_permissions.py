"""Tests for gateway group-level regex permission repositories (endpoint, secret, model definition)."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.repository.gateway_endpoint_group_regex_permissions import (
    GatewayEndpointPermissionGroupRegexRepository,
)
from mlflow_oidc_auth.repository.gateway_secret_group_regex_permissions import (
    GatewaySecretPermissionGroupRegexRepository,
)
from mlflow_oidc_auth.repository.gateway_model_definition_group_regex_permissions import (
    GatewayModelDefinitionPermissionGroupRegexRepository,
)

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
        GatewayEndpointPermissionGroupRegexRepository,
        "mlflow_oidc_auth.repository.gateway_endpoint_group_regex_permissions",
        "_get_group_regex_permission",
        "SqlGatewayEndpointGroupRegexPermission",
        id="endpoint",
    ),
    pytest.param(
        GatewaySecretPermissionGroupRegexRepository,
        "mlflow_oidc_auth.repository.gateway_secret_group_regex_permissions",
        "_get_group_regex_permission",
        "SqlGatewaySecretGroupRegexPermission",
        id="secret",
    ),
    pytest.param(
        GatewayModelDefinitionPermissionGroupRegexRepository,
        "mlflow_oidc_auth.repository.gateway_model_definition_group_regex_permissions",
        "_get_group_regex_permission",
        "SqlGatewayModelDefinitionGroupRegexPermission",
        id="model_definition",
    ),
]


# ---------------------------------------------------------------------------
# Tests — _get_group_regex_permission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestGetGroupRegexPermission:
    """Tests for _get_group_regex_permission private helper."""

    def test_found(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test successful lookup returns the row."""
        repo = repo_cls(session_maker)
        perm = MagicMock()
        session.query().filter().one.return_value = perm
        assert repo._get_group_regex_permission(session, 1, 10) == perm

    def test_not_found(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test NoResultFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().filter().one.side_effect = NoResultFound()
        with pytest.raises(MlflowException) as exc:
            repo._get_group_regex_permission(session, 1, 10)
        assert exc.value.error_code == "RESOURCE_DOES_NOT_EXIST"

    def test_multiple_found(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test MultipleResultsFound raises MlflowException."""
        repo = repo_cls(session_maker)
        session.query().filter().one.side_effect = MultipleResultsFound()
        with pytest.raises(MlflowException) as exc:
            repo._get_group_regex_permission(session, 1, 10)
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
        group = MagicMock(id=10)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{mod}.get_group", return_value=group),
            patch(f"{mod}.{sql_cls}", return_value=perm),
            patch(f"{mod}._validate_permission"),
        ):
            result = repo.grant("devs", "regex-.*", 1, "READ")
        assert result == "entity"
        session.add.assert_called_once_with(perm)
        session.flush.assert_called_once()

    def test_integrity_error(self, session_maker, session, repo_cls, mod, getter, sql_cls):
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
                repo.grant("devs", "regex-.*", 1, "READ")
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
        group = MagicMock(id=10)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{mod}.get_group", return_value=group),
            patch.object(repo, getter, return_value=perm),
        ):
            assert repo.get(1, "devs") == "entity"


# ---------------------------------------------------------------------------
# Tests — list_permissions_for_group
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestListPermissionsForGroup:
    """Tests for list_permissions_for_group."""

    def test_returns_entities(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test list returns mapped entities ordered by priority."""
        repo = repo_cls(session_maker)
        group = MagicMock(id=10)
        perm1 = MagicMock()
        perm1.to_mlflow_entity.return_value = "e1"
        session.query().filter().order_by().all.return_value = [perm1]
        with patch(f"{mod}.get_group", return_value=group):
            result = repo.list_permissions_for_group("devs")
        assert result == ["e1"]


# ---------------------------------------------------------------------------
# Tests — list_permissions_for_groups
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestListPermissionsForGroups:
    """Tests for list_permissions_for_groups."""

    def test_returns_entities(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test list_permissions_for_groups returns entities for multiple groups."""
        repo = repo_cls(session_maker)
        g1 = MagicMock(id=10)
        g2 = MagicMock(id=20)
        perm1 = MagicMock()
        perm1.to_mlflow_entity.return_value = "e1"
        perm2 = MagicMock()
        perm2.to_mlflow_entity.return_value = "e2"
        session.query().filter().order_by().all.return_value = [perm1, perm2]
        with patch(f"{mod}.get_group", side_effect=[g1, g2]):
            result = repo.list_permissions_for_groups(["devs", "admins"])
        assert result == ["e1", "e2"]

    def test_empty_groups(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test with empty group list."""
        repo = repo_cls(session_maker)
        session.query().filter().order_by().all.return_value = []
        result = repo.list_permissions_for_groups([])
        assert result == []


# ---------------------------------------------------------------------------
# Tests — list_permissions_for_groups_ids
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestListPermissionsForGroupsIds:
    """Tests for list_permissions_for_groups_ids."""

    def test_returns_entities(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test list by group IDs returns mapped entities."""
        repo = repo_cls(session_maker)
        perm1 = MagicMock()
        perm1.to_mlflow_entity.return_value = "e1"
        session.query().filter().order_by().all.return_value = [perm1]
        result = repo.list_permissions_for_groups_ids([10, 20])
        assert result == ["e1"]

    def test_empty_ids(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test with empty IDs list."""
        repo = repo_cls(session_maker)
        session.query().filter().order_by().all.return_value = []
        result = repo.list_permissions_for_groups_ids([])
        assert result == []


# ---------------------------------------------------------------------------
# Tests — update
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("repo_cls,mod,getter,sql_cls", RESOURCE_CONFIGS)
class TestUpdate:
    """Tests for update."""

    def test_success(self, session_maker, session, repo_cls, mod, getter, sql_cls):
        """Test successful update sets priority, permission and commits."""
        repo = repo_cls(session_maker)
        group = MagicMock(id=10)
        perm = MagicMock()
        perm.to_mlflow_entity.return_value = "entity"
        with (
            patch(f"{mod}.get_group", return_value=group),
            patch.object(repo, getter, return_value=perm),
            patch(f"{mod}._validate_permission"),
        ):
            result = repo.update(1, "devs", "new-.*", 5, "MANAGE")
        assert result == "entity"
        assert perm.priority == 5
        assert perm.permission == "MANAGE"
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
        group = MagicMock(id=10)
        perm = MagicMock()
        with (
            patch(f"{mod}.get_group", return_value=group),
            patch.object(repo, getter, return_value=perm),
        ):
            assert repo.revoke(1, "devs") is None
        session.delete.assert_called_once_with(perm)
        session.commit.assert_called_once()
