"""Tests for the user permissions router.

These tests focus on response shapes now that the router returns typed models
(via response_model) instead of ad-hoc JSONResponse payloads.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.entities import RegisteredModelPermission as RegisteredModelPermissionEntity
from mlflow_oidc_auth.entities import RegisteredModelRegexPermission as RegisteredModelRegexPermissionEntity
from mlflow_oidc_auth.entities import ScorerPermission as ScorerPermissionEntity
from mlflow_oidc_auth.entities import ScorerRegexPermission as ScorerRegexPermissionEntity


@pytest.mark.usefixtures("authenticated_session")
class TestUserPermissionsRoutes:
    def test_list_user_prompts_returns_typed_shape(self, authenticated_client):
        prompt_a = MagicMock()
        prompt_a.name = "prompt-a"
        prompt_b = MagicMock()
        prompt_b.name = "prompt-b"

        perm_result = MagicMock()
        perm_result.permission.name = "READ"
        perm_result.kind = "user"

        # Mock batch_resolve_prompt_permissions to return a dict mapping name to perm_result
        mock_permissions = {"prompt-a": perm_result, "prompt-b": perm_result}

        with (
            patch("mlflow_oidc_auth.routers.user_permissions.fetch_all_prompts", return_value=[prompt_a, prompt_b]),
            patch("mlflow_oidc_auth.routers.user_permissions.batch_resolve_prompt_permissions", return_value=mock_permissions),
        ):
            resp = authenticated_client.get("/api/2.0/mlflow/permissions/users/user@example.com/prompts")

        assert resp.status_code == 200
        body = resp.json()
        assert body == [
            {"name": "prompt-a", "permission": "READ", "kind": "user"},
            {"name": "prompt-b", "permission": "READ", "kind": "user"},
        ]

    def test_get_user_prompt_permission_returns_wrapper(self, authenticated_client, mock_store):
        mock_store.get_registered_model_permission.return_value = RegisteredModelPermissionEntity(
            name="prompt-a",
            permission="MANAGE",
            user_id=123,
            group_id=None,
            prompt=True,
        )

        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get("/api/2.0/mlflow/permissions/users/user@example.com/prompts/prompt-a")

        assert resp.status_code == 200
        assert resp.json() == {"prompt_permission": {"name": "prompt-a", "user_id": 123, "permission": "MANAGE", "group_id": None, "prompt": True}}

    def test_list_user_prompt_patterns_returns_typed_records(self, admin_client, mock_store):
        mock_store.list_prompt_regex_permissions.return_value = [
            RegisteredModelRegexPermissionEntity(id_=1, regex=".*", priority=1, user_id=123, permission="READ", prompt=True),
            RegisteredModelRegexPermissionEntity(id_=2, regex="^x$", priority=2, user_id=123, permission="MANAGE", prompt=True),
        ]

        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = admin_client.get("/api/2.0/mlflow/permissions/users/user@example.com/prompts-patterns")

        assert resp.status_code == 200
        assert resp.json() == [
            {"id": 1, "regex": ".*", "priority": 1, "user_id": 123, "permission": "READ", "prompt": True},
            {"id": 2, "regex": "^x$", "priority": 2, "user_id": 123, "permission": "MANAGE", "prompt": True},
        ]

    def test_list_user_scorer_permissions_returns_typed_records(self, authenticated_client, mock_store):
        mock_store.list_scorer_permissions.return_value = [
            ScorerPermissionEntity(experiment_id="1", scorer_name="s1", user_id=123, permission="READ"),
            ScorerPermissionEntity(experiment_id="1", scorer_name="s2", user_id=123, permission="MANAGE"),
        ]

        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = authenticated_client.get("/api/2.0/mlflow/permissions/users/user@example.com/scorers")

        assert resp.status_code == 200
        assert resp.json() == [
            {"experiment_id": "1", "scorer_name": "s1", "user_id": 123, "permission": "READ"},
            {"experiment_id": "1", "scorer_name": "s2", "user_id": 123, "permission": "MANAGE"},
        ]

    def test_list_user_scorer_patterns_returns_typed_records(self, admin_client, mock_store):
        mock_store.list_scorer_regex_permissions.return_value = [
            ScorerRegexPermissionEntity(id_=1, regex=".*", priority=1, user_id=123, permission="READ"),
        ]

        with patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store):
            resp = admin_client.get("/api/2.0/mlflow/permissions/users/user@example.com/scorer-patterns")

        assert resp.status_code == 200
        assert resp.json() == [{"id": 1, "regex": ".*", "priority": 1, "user_id": 123, "permission": "READ"}]
