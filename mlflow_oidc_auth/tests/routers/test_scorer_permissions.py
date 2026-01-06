import pytest


@pytest.mark.usefixtures("authenticated_session")
class TestScorerPermissionRoutes:
    def test_create_scorer_permission(self, authenticated_client, mock_store):
        mock_store.create_scorer_permission.return_value.to_json.return_value = {
            "experiment_id": "123",
            "scorer_name": "my_scorer",
            "user_id": 2,
            "permission": "MANAGE",
        }

        resp = authenticated_client.post(
            "/api/3.0/mlflow/permissions/scorers/create",
            json={"experiment_id": "123", "scorer_name": "my_scorer", "username": "user@example.com", "permission": "MANAGE"},
        )

        assert resp.status_code == 200
        assert resp.json()["scorer_permission"]["experiment_id"] == "123"
        mock_store.create_scorer_permission.assert_called_once_with(
            experiment_id="123",
            scorer_name="my_scorer",
            username="user@example.com",
            permission="MANAGE",
        )

    def test_get_scorer_permission(self, authenticated_client, mock_store):
        mock_store.get_scorer_permission.return_value.to_json.return_value = {
            "experiment_id": "123",
            "scorer_name": "my_scorer",
            "user_id": 2,
            "permission": "READ",
        }

        resp = authenticated_client.get(
            "/api/3.0/mlflow/permissions/scorers/get",
            params={"experiment_id": "123", "scorer_name": "my_scorer", "username": "user@example.com"},
        )

        assert resp.status_code == 200
        assert resp.json()["scorer_permission"]["permission"] == "READ"
        mock_store.get_scorer_permission.assert_called_once_with("123", "my_scorer", "user@example.com")

    def test_update_scorer_permission(self, authenticated_client, mock_store):
        resp = authenticated_client.patch(
            "/api/3.0/mlflow/permissions/scorers/update",
            json={"experiment_id": "123", "scorer_name": "my_scorer", "username": "user@example.com", "permission": "UPDATE"},
        )

        assert resp.status_code == 200
        assert resp.json() == {}
        mock_store.update_scorer_permission.assert_called_once_with(
            experiment_id="123",
            scorer_name="my_scorer",
            username="user@example.com",
            permission="UPDATE",
        )

    def test_delete_scorer_permission(self, authenticated_client, mock_store):
        resp = authenticated_client.delete(
            "/api/3.0/mlflow/permissions/scorers/delete",
            json={"experiment_id": "123", "scorer_name": "my_scorer", "username": "user@example.com", "permission": "READ"},
        )

        assert resp.status_code == 200
        assert resp.json() == {}
        mock_store.delete_scorer_permission.assert_called_once_with("123", "my_scorer", "user@example.com")

    def test_list_scorer_groups(self, authenticated_client, mock_store):
        mock_store.scorer_group_repo.list_groups_for_scorer.return_value = [("my-group", "READ"), ("admins", "MANAGE")]

        resp = authenticated_client.get("/api/3.0/mlflow/permissions/scorers/123/my_scorer/groups")

        assert resp.status_code == 200
        body = resp.json()
        assert body == [
            {"group_name": "my-group", "permission": "READ"},
            {"group_name": "admins", "permission": "MANAGE"},
        ]
        mock_store.scorer_group_repo.list_groups_for_scorer.assert_called_once_with("123", "my_scorer")
