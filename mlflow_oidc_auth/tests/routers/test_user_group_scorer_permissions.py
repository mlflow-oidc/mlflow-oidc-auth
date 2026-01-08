import pytest


@pytest.mark.usefixtures("authenticated_session")
class TestUserScorerPermissionRoutes:
    def test_list_user_scorer_permissions_admin(self, admin_client, mock_store):
        perm = mock_store.list_scorer_permissions.return_value
        perm.__iter__.return_value = iter([])

        mock_store.list_scorer_permissions.return_value = []

        resp = admin_client.get("/api/2.0/mlflow/permissions/users/user@example.com/scorers")

        assert resp.status_code == 200
        assert resp.json() == []
        mock_store.list_scorer_permissions.assert_called_once_with(username="user@example.com")

    def test_create_user_scorer_permission(self, authenticated_client, mock_store):
        mock_store.create_scorer_permission.return_value.to_json.return_value = {
            "experiment_id": "123",
            "scorer_name": "my_scorer",
            "user_id": 2,
            "permission": "MANAGE",
        }

        resp = authenticated_client.post(
            "/api/2.0/mlflow/permissions/users/user@example.com/scorers/123/my_scorer",
            json={"permission": "MANAGE"},
        )

        assert resp.status_code == 201
        assert resp.json()["scorer_permission"]["experiment_id"] == "123"
        mock_store.create_scorer_permission.assert_called_once_with(
            experiment_id="123",
            scorer_name="my_scorer",
            username="user@example.com",
            permission="MANAGE",
        )

    def test_get_user_scorer_permission(self, authenticated_client, mock_store):
        mock_store.get_scorer_permission.return_value.to_json.return_value = {
            "experiment_id": "123",
            "scorer_name": "my_scorer",
            "user_id": 2,
            "permission": "READ",
        }

        resp = authenticated_client.get("/api/2.0/mlflow/permissions/users/user@example.com/scorers/123/my_scorer")

        assert resp.status_code == 200
        assert resp.json()["scorer_permission"]["permission"] == "READ"
        mock_store.get_scorer_permission.assert_called_once_with("123", "my_scorer", "user@example.com")

    def test_update_user_scorer_permission(self, authenticated_client, mock_store):
        resp = authenticated_client.patch(
            "/api/2.0/mlflow/permissions/users/user@example.com/scorers/123/my_scorer",
            json={"permission": "UPDATE"},
        )

        assert resp.status_code == 200
        mock_store.update_scorer_permission.assert_called_once_with(
            experiment_id="123",
            scorer_name="my_scorer",
            username="user@example.com",
            permission="UPDATE",
        )

    def test_delete_user_scorer_permission(self, authenticated_client, mock_store):
        resp = authenticated_client.delete("/api/2.0/mlflow/permissions/users/user@example.com/scorers/123/my_scorer")

        assert resp.status_code == 200
        mock_store.delete_scorer_permission.assert_called_once_with("123", "my_scorer", "user@example.com")


class TestUserScorerPatternRoutes:
    def test_list_user_scorer_patterns_admin(self, admin_client, mock_store):
        mock_store.list_scorer_regex_permissions.return_value = []

        resp = admin_client.get("/api/2.0/mlflow/permissions/users/user@example.com/scorer-patterns")

        assert resp.status_code == 200
        assert resp.json() == []
        mock_store.list_scorer_regex_permissions.assert_called_once_with(username="user@example.com")

    def test_create_user_scorer_pattern_admin(self, admin_client, mock_store):
        mock_store.create_scorer_regex_permission.return_value.to_json.return_value = {
            "id": 1,
            "regex": "exp_.*",
            "priority": 1,
            "user_id": 2,
            "permission": "READ",
        }

        resp = admin_client.post(
            "/api/2.0/mlflow/permissions/users/user@example.com/scorer-patterns",
            json={"regex": "exp_.*", "priority": 1, "permission": "READ"},
        )

        assert resp.status_code == 201
        assert resp.json()["pattern"]["id"] == 1
        mock_store.create_scorer_regex_permission.assert_called_once_with(
            regex="exp_.*",
            priority=1,
            permission="READ",
            username="user@example.com",
        )

    def test_get_user_scorer_pattern_admin(self, admin_client, mock_store):
        mock_store.get_scorer_regex_permission.return_value.to_json.return_value = {
            "id": 1,
            "regex": "exp_.*",
            "priority": 1,
            "user_id": 2,
            "permission": "READ",
        }

        resp = admin_client.get("/api/2.0/mlflow/permissions/users/user@example.com/scorer-patterns/1")

        assert resp.status_code == 200
        assert resp.json()["pattern"]["id"] == 1
        mock_store.get_scorer_regex_permission.assert_called_once_with(username="user@example.com", id=1)

    def test_update_user_scorer_pattern_admin(self, admin_client, mock_store):
        mock_store.update_scorer_regex_permission.return_value.to_json.return_value = {
            "id": 1,
            "regex": "exp_.*",
            "priority": 2,
            "user_id": 2,
            "permission": "MANAGE",
        }

        resp = admin_client.patch(
            "/api/2.0/mlflow/permissions/users/user@example.com/scorer-patterns/1",
            json={"regex": "exp_.*", "priority": 2, "permission": "MANAGE"},
        )

        assert resp.status_code == 200
        assert resp.json()["pattern"]["priority"] == 2
        mock_store.update_scorer_regex_permission.assert_called_once_with(
            id=1,
            regex="exp_.*",
            priority=2,
            permission="MANAGE",
            username="user@example.com",
        )

    def test_delete_user_scorer_pattern_admin(self, admin_client, mock_store):
        resp = admin_client.delete("/api/2.0/mlflow/permissions/users/user@example.com/scorer-patterns/1")

        assert resp.status_code == 200
        mock_store.delete_scorer_regex_permission.assert_called_once_with(id=1, username="user@example.com")


@pytest.mark.usefixtures("authenticated_session")
class TestGroupScorerPermissionRoutes:
    def test_list_group_scorer_permissions_admin(self, admin_client, mock_store):
        mock_store.list_group_scorer_permissions.return_value = []

        resp = admin_client.get("/api/2.0/mlflow/permissions/groups/my-group/scorers")

        assert resp.status_code == 200
        assert resp.json() == []
        mock_store.list_group_scorer_permissions.assert_called_once_with("my-group")

    def test_create_group_scorer_permission(self, authenticated_client, mock_store):
        resp = authenticated_client.post(
            "/api/2.0/mlflow/permissions/groups/my-group/scorers/123/my_scorer",
            json={"permission": "MANAGE"},
        )

        assert resp.status_code == 201
        mock_store.create_group_scorer_permission.assert_called_once_with(
            group_name="my-group",
            experiment_id="123",
            scorer_name="my_scorer",
            permission="MANAGE",
        )

    def test_update_group_scorer_permission(self, authenticated_client, mock_store):
        resp = authenticated_client.patch(
            "/api/2.0/mlflow/permissions/groups/my-group/scorers/123/my_scorer",
            json={"permission": "READ"},
        )

        assert resp.status_code == 200
        mock_store.update_group_scorer_permission.assert_called_once_with(
            group_name="my-group",
            experiment_id="123",
            scorer_name="my_scorer",
            permission="READ",
        )

    def test_delete_group_scorer_permission(self, authenticated_client, mock_store):
        resp = authenticated_client.delete("/api/2.0/mlflow/permissions/groups/my-group/scorers/123/my_scorer")

        assert resp.status_code == 200
        mock_store.delete_group_scorer_permission.assert_called_once_with("my-group", "123", "my_scorer")


class TestGroupScorerPatternRoutes:
    def test_list_group_scorer_patterns_admin(self, admin_client, mock_store):
        mock_store.list_group_scorer_regex_permissions.return_value = []

        resp = admin_client.get("/api/2.0/mlflow/permissions/groups/my-group/scorer-patterns")

        assert resp.status_code == 200
        assert resp.json() == []
        mock_store.list_group_scorer_regex_permissions.assert_called_once_with("my-group")

    def test_create_group_scorer_pattern_admin(self, admin_client, mock_store):
        mock_store.create_group_scorer_regex_permission.return_value.to_json.return_value = {
            "id": 1,
            "regex": ".*",
            "priority": 1,
            "permission": "READ",
            "group_name": "my-group",
        }

        resp = admin_client.post(
            "/api/2.0/mlflow/permissions/groups/my-group/scorer-patterns",
            json={"regex": ".*", "priority": 1, "permission": "READ"},
        )

        assert resp.status_code == 201
        assert resp.json()["status"] == "success"
        mock_store.create_group_scorer_regex_permission.assert_called_once_with(
            group_name="my-group",
            regex=".*",
            priority=1,
            permission="READ",
        )

    def test_get_group_scorer_pattern_admin(self, admin_client, mock_store):
        mock_store.get_group_scorer_regex_permission.return_value.to_json.return_value = {
            "id": 1,
            "regex": ".*",
            "priority": 1,
            "permission": "READ",
            "group_name": "my-group",
        }

        resp = admin_client.get("/api/2.0/mlflow/permissions/groups/my-group/scorer-patterns/1")

        assert resp.status_code == 200
        assert resp.json()["id"] == 1
        mock_store.get_group_scorer_regex_permission.assert_called_once_with("my-group", 1)

    def test_update_group_scorer_pattern_admin(self, admin_client, mock_store):
        resp = admin_client.patch(
            "/api/2.0/mlflow/permissions/groups/my-group/scorer-patterns/1",
            json={"regex": "x.*", "priority": 2, "permission": "MANAGE"},
        )

        assert resp.status_code == 200
        mock_store.update_group_scorer_regex_permission.assert_called_once_with(
            id=1,
            group_name="my-group",
            regex="x.*",
            priority=2,
            permission="MANAGE",
        )

    def test_delete_group_scorer_pattern_admin(self, admin_client, mock_store):
        resp = admin_client.delete("/api/2.0/mlflow/permissions/groups/my-group/scorer-patterns/1")

        assert resp.status_code == 200
        mock_store.delete_group_scorer_regex_permission.assert_called_once_with(1, "my-group")
