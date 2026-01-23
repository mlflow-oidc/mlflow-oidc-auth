from unittest.mock import AsyncMock, MagicMock

import pytest

from mlflow_oidc_auth.entities import ScorerPermission


@pytest.mark.usefixtures("authenticated_session")
class TestScorerPermissionRoutes:
    def test_list_scorers_admin_sees_all(self, authenticated_client, monkeypatch):
        scorer_one = MagicMock(
            experiment_id="exp-1",
            scorer_name="alpha",
            scorer_version=1,
            creation_time=111,
            scorer_id="s-1",
        )
        scorer_two = MagicMock(
            experiment_id="exp-1",
            scorer_name="beta",
            scorer_version=2,
            creation_time=222,
            scorer_id="s-2",
        )

        tracking_store = MagicMock()
        tracking_store.list_scorers.return_value = [scorer_one, scorer_two]

        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions._get_tracking_store", MagicMock(return_value=tracking_store))
        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions.get_username", AsyncMock(return_value="admin@example.com"))
        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions.get_is_admin", AsyncMock(return_value=True))

        resp = authenticated_client.get("/api/3.0/mlflow/permissions/scorers/exp-1")

        assert resp.status_code == 200
        assert resp.json() == [
            {"experiment_id": "exp-1", "name": "alpha", "version": 1, "creation_time": 111, "scorer_id": "s-1"},
            {"experiment_id": "exp-1", "name": "beta", "version": 2, "creation_time": 222, "scorer_id": "s-2"},
        ]
        tracking_store.list_scorers.assert_called_once_with("exp-1")

    def test_list_scorers_filters_by_permission(self, authenticated_client, monkeypatch):
        scorer_one = MagicMock(
            experiment_id="exp-1",
            scorer_name="alpha",
            scorer_version=1,
            creation_time=111,
            scorer_id="s-1",
        )
        scorer_two = MagicMock(
            experiment_id="exp-1",
            scorer_name="beta",
            scorer_version=2,
            creation_time=222,
            scorer_id="s-2",
        )

        tracking_store = MagicMock()
        tracking_store.list_scorers.return_value = [scorer_one, scorer_two]

        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions._get_tracking_store", MagicMock(return_value=tracking_store))
        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions.get_username", AsyncMock(return_value="user@example.com"))
        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions.get_is_admin", AsyncMock(return_value=False))

        def _can_manage(experiment_id: str, scorer_name: str, username: str) -> bool:
            return scorer_name == "alpha"

        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions.can_manage_scorer", _can_manage)

        resp = authenticated_client.get("/api/3.0/mlflow/permissions/scorers/exp-1")

        assert resp.status_code == 200
        assert resp.json() == [{"experiment_id": "exp-1", "name": "alpha", "version": 1, "creation_time": 111, "scorer_id": "s-1"}]

    def test_list_scorers_handles_backend_error(self, authenticated_client, monkeypatch):
        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions._get_tracking_store", MagicMock(side_effect=Exception("boom")))
        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions.get_username", AsyncMock(return_value="user@example.com"))
        monkeypatch.setattr("mlflow_oidc_auth.routers.scorers_permissions.get_is_admin", AsyncMock(return_value=False))

        resp = authenticated_client.get("/api/3.0/mlflow/permissions/scorers/exp-1")

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to retrieve scorers"

    def test_list_scorer_groups(self, authenticated_client, mock_store):
        mock_store.scorer_group_repo.list_groups_for_scorer.return_value = [("my-group", "READ"), ("admins", "MANAGE")]

        resp = authenticated_client.get("/api/3.0/mlflow/permissions/scorers/123/my_scorer/groups")

        assert resp.status_code == 200
        body = resp.json()
        assert body == [
            {"name": "my-group", "permission": "READ", "kind": "group"},
            {"name": "admins", "permission": "MANAGE", "kind": "group"},
        ]
        mock_store.scorer_group_repo.list_groups_for_scorer.assert_called_once_with("123", "my_scorer")

    def test_list_scorer_groups_handles_backend_error(self, authenticated_client, mock_store):
        mock_store.scorer_group_repo.list_groups_for_scorer.side_effect = Exception("db down")

        resp = authenticated_client.get("/api/3.0/mlflow/permissions/scorers/123/my_scorer/groups")

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to retrieve scorer group permissions"

    def test_list_scorer_users(self, authenticated_client, mock_store):
        _admin_user, regular_user, service_user = mock_store.list_users.return_value
        regular_user.scorer_permissions = [ScorerPermission("123", "my_scorer", regular_user.id, "READ")]
        service_user.scorer_permissions = [ScorerPermission("123", "my_scorer", service_user.id, "MANAGE")]

        resp = authenticated_client.get("/api/3.0/mlflow/permissions/scorers/123/my_scorer/users")

        assert resp.status_code == 200
        assert resp.json() == [
            {"name": "user@example.com", "permission": "READ", "kind": "user"},
            {"name": "service@example.com", "permission": "MANAGE", "kind": "service-account"},
        ]
        mock_store.list_users.assert_called_once_with(all=True)

    def test_list_scorer_users_handles_backend_error(self, authenticated_client, mock_store):
        mock_store.list_users.side_effect = Exception("db offline")

        resp = authenticated_client.get("/api/3.0/mlflow/permissions/scorers/123/my_scorer/users")

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to retrieve scorer user permissions"
