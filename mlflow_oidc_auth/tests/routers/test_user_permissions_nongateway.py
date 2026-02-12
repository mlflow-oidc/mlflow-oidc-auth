"""Tests for non-gateway endpoints in user_permissions router.

Covers experiments, registered models, prompts, scorers (direct + pattern variants).
Scorer and prompt tests in test_user_permissions.py are not duplicated here.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.dependencies import check_admin_permission, check_experiment_manage_permission, check_registered_model_manage_permission
from mlflow_oidc_auth.entities import ExperimentPermission as ExperimentPermissionEntity
from mlflow_oidc_auth.entities import RegisteredModelPermission as RegisteredModelPermissionEntity
from mlflow_oidc_auth.entities import RegisteredModelRegexPermission as RegisteredModelRegexPermissionEntity

USER_BASE = "/api/2.0/mlflow/permissions/users"

# Module path for patching imports at the router module level
_UP = "mlflow_oidc_auth.routers.user_permissions"


@pytest.fixture
def override_admin(test_app):
    """Override admin permission check to always pass."""

    async def always_admin():
        return "admin@example.com"

    test_app.dependency_overrides[check_admin_permission] = always_admin
    yield
    test_app.dependency_overrides.pop(check_admin_permission, None)


@pytest.fixture
def override_experiment_manage(test_app):
    """Override experiment manage permission check."""

    async def always_manage():
        return "admin@example.com"

    test_app.dependency_overrides[check_experiment_manage_permission] = always_manage
    yield
    test_app.dependency_overrides.pop(check_experiment_manage_permission, None)


@pytest.fixture
def override_model_manage(test_app):
    """Override registered model manage permission check."""

    async def always_manage():
        return "admin@example.com"

    test_app.dependency_overrides[check_registered_model_manage_permission] = always_manage
    yield
    test_app.dependency_overrides.pop(check_registered_model_manage_permission, None)


# ========================================================================================
# USER EXPERIMENT PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session")
class TestUserExperimentList:
    """Tests for get_user_experiment_permissions (list) endpoint."""

    def test_list_experiments_as_admin(self, admin_client, mock_store):
        """Admin sees all experiments with permissions."""
        mock_exp = MagicMock()
        mock_exp.experiment_id = "123"
        mock_exp.name = "Test Exp"

        perm_result = MagicMock()
        perm_result.permission.name = "MANAGE"
        perm_result.kind = "user"
        mock_permissions_map = {"123": perm_result}

        with (
            patch(f"{_UP}._get_tracking_store") as mock_ts,
            patch(f"{_UP}.batch_resolve_experiment_permissions", return_value=mock_permissions_map),
        ):
            mock_ts.return_value.search_experiments.return_value = [mock_exp]
            resp = admin_client.get(f"{USER_BASE}/user@example.com/experiments")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == "123"
        assert body[0]["permission"] == "MANAGE"


@pytest.mark.usefixtures("authenticated_session", "override_experiment_manage")
class TestUserExperimentCRUD:
    """Tests for create/get/update/delete user experiment permissions."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating experiment permission for a user."""
        resp = authenticated_client.post(f"{USER_BASE}/user@example.com/experiments/exp-1", json={"permission": "READ"})
        assert resp.status_code == 200
        mock_store.create_experiment_permission.assert_called_once()

    def test_get(self, authenticated_client, mock_store):
        """Test getting experiment permission for a user."""
        ep = ExperimentPermissionEntity(experiment_id="exp-1", permission="READ", user_id=2)
        mock_store.get_experiment_permission.return_value = ep
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/experiments/exp-1")
        assert resp.status_code == 200
        assert resp.json()["experiment_permission"]["experiment_id"] == "exp-1"

    def test_update(self, authenticated_client, mock_store):
        """Test updating experiment permission for a user."""
        resp = authenticated_client.patch(f"{USER_BASE}/user@example.com/experiments/exp-1", json={"permission": "EDIT"})
        assert resp.status_code == 200
        mock_store.update_experiment_permission.assert_called_once()

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting experiment permission for a user."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/experiments/exp-1")
        assert resp.status_code == 200
        mock_store.delete_experiment_permission.assert_called_once()


# ========================================================================================
# USER EXPERIMENT PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserExperimentPatterns:
    """Tests for user experiment regex/pattern permission CRUD."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing experiment regex permissions."""
        perm = MagicMock()
        perm.id = 1
        perm.regex = "exp-.*"
        perm.priority = 1
        perm.permission = "READ"
        mock_store.list_experiment_regex_permissions.return_value = [perm]
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/experiment-patterns")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["regex"] == "exp-.*"

    def test_list_error(self, authenticated_client, mock_store):
        """Test error handling for list."""
        mock_store.list_experiment_regex_permissions.side_effect = Exception("DB error")
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/experiment-patterns")
        assert resp.status_code == 500

    def test_create(self, authenticated_client, mock_store):
        """Test creating experiment regex permission."""
        resp = authenticated_client.post(
            f"{USER_BASE}/user@example.com/experiment-patterns",
            json={"regex": "exp-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 201
        mock_store.create_experiment_regex_permission.assert_called_once()

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_experiment_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(
            f"{USER_BASE}/user@example.com/experiment-patterns",
            json={"regex": "exp-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 500

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific experiment regex permission."""
        perm = MagicMock()
        perm.id = 1
        perm.regex = "exp-.*"
        perm.priority = 1
        perm.permission = "READ"
        mock_store.get_experiment_regex_permission.return_value = perm
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/experiment-patterns/1")
        assert resp.status_code == 200

    def test_get_invalid_id(self, authenticated_client, mock_store):
        """Test getting with invalid (non-integer) pattern ID."""
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/experiment-patterns/abc")
        assert resp.status_code == 400

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test getting non-existent pattern."""
        mock_store.get_experiment_regex_permission.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/experiment-patterns/1")
        assert resp.status_code == 404

    def test_update(self, authenticated_client, mock_store):
        """Test updating experiment regex permission."""
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/experiment-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 200
        mock_store.update_experiment_regex_permission.assert_called_once()

    def test_update_invalid_id(self, authenticated_client, mock_store):
        """Test updating with invalid (non-integer) pattern ID."""
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/experiment-patterns/abc",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 400

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_experiment_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/experiment-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting experiment regex permission."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/experiment-patterns/1")
        assert resp.status_code == 200
        mock_store.delete_experiment_regex_permission.assert_called_once()

    def test_delete_invalid_id(self, authenticated_client, mock_store):
        """Test deleting with invalid (non-integer) pattern ID."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/experiment-patterns/abc")
        assert resp.status_code == 400

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_experiment_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/experiment-patterns/1")
        assert resp.status_code == 500


# ========================================================================================
# USER REGISTERED MODEL PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session")
class TestUserRegisteredModelList:
    """Tests for get_user_registered_models (list) endpoint."""

    def test_list_models_as_admin(self, admin_client, mock_store):
        """Admin sees all registered models with permissions."""
        mock_model = MagicMock()
        mock_model.name = "my-model"

        perm_result = MagicMock()
        perm_result.permission.name = "READ"
        perm_result.kind = "user"
        mock_permissions_map = {"my-model": perm_result}

        with (
            patch(f"{_UP}.fetch_all_registered_models", return_value=[mock_model]),
            patch(f"{_UP}.batch_resolve_model_permissions", return_value=mock_permissions_map),
        ):
            resp = admin_client.get(f"{USER_BASE}/user@example.com/registered-models")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "my-model"
        assert body[0]["permission"] == "READ"


@pytest.mark.usefixtures("authenticated_session", "override_model_manage")
class TestUserRegisteredModelCRUD:
    """Tests for create/get/update/delete user registered model permissions."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating registered model permission for a user."""
        resp = authenticated_client.post(f"{USER_BASE}/user@example.com/registered-models/my-model", json={"permission": "READ"})
        assert resp.status_code == 201
        mock_store.create_registered_model_permission.assert_called_once()

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_registered_model_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(f"{USER_BASE}/user@example.com/registered-models/my-model", json={"permission": "READ"})
        assert resp.status_code == 500

    def test_get(self, authenticated_client, mock_store):
        """Test getting registered model permission for a user."""
        rmp = RegisteredModelPermissionEntity(name="my-model", permission="READ", user_id=2)
        mock_store.get_registered_model_permission.return_value = rmp
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/registered-models/my-model")
        assert resp.status_code == 200
        assert resp.json()["registered_model_permission"]["name"] == "my-model"

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test getting non-existent permission."""
        mock_store.get_registered_model_permission.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/registered-models/my-model")
        assert resp.status_code == 404

    def test_update(self, authenticated_client, mock_store):
        """Test updating registered model permission for a user."""
        resp = authenticated_client.patch(f"{USER_BASE}/user@example.com/registered-models/my-model", json={"permission": "EDIT"})
        assert resp.status_code == 200
        mock_store.update_registered_model_permission.assert_called_once()

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_registered_model_permission.side_effect = Exception("DB error")
        resp = authenticated_client.patch(f"{USER_BASE}/user@example.com/registered-models/my-model", json={"permission": "EDIT"})
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting registered model permission for a user."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/registered-models/my-model")
        assert resp.status_code == 200
        mock_store.delete_registered_model_permission.assert_called_once()

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_registered_model_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/registered-models/my-model")
        assert resp.status_code == 500


# ========================================================================================
# USER REGISTERED MODEL PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserRegisteredModelPatterns:
    """Tests for user registered model regex/pattern permission CRUD."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing registered model regex permissions."""
        rmp = RegisteredModelRegexPermissionEntity(id_=1, regex="model-.*", priority=1, user_id=2, permission="READ")
        mock_store.list_registered_model_regex_permissions.return_value = [rmp]
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/registered-models-patterns")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["regex"] == "model-.*"

    def test_list_error(self, authenticated_client, mock_store):
        """Test error handling for list."""
        mock_store.list_registered_model_regex_permissions.side_effect = Exception("DB error")
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/registered-models-patterns")
        assert resp.status_code == 500

    def test_create(self, authenticated_client, mock_store):
        """Test creating registered model regex permission."""
        resp = authenticated_client.post(
            f"{USER_BASE}/user@example.com/registered-models-patterns",
            json={"regex": "model-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 201
        mock_store.create_registered_model_regex_permission.assert_called_once()

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_registered_model_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(
            f"{USER_BASE}/user@example.com/registered-models-patterns",
            json={"regex": "model-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 500

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific registered model regex permission."""
        rmp = RegisteredModelRegexPermissionEntity(id_=1, regex="model-.*", priority=1, user_id=2, permission="READ")
        mock_store.get_registered_model_regex_permission.return_value = rmp
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/registered-models-patterns/1")
        assert resp.status_code == 200

    def test_get_invalid_id(self, authenticated_client, mock_store):
        """Test getting with invalid (non-integer) pattern ID."""
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/registered-models-patterns/abc")
        assert resp.status_code == 400

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test getting non-existent pattern."""
        mock_store.get_registered_model_regex_permission.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/registered-models-patterns/1")
        assert resp.status_code == 404

    def test_update(self, authenticated_client, mock_store):
        """Test updating registered model regex permission."""
        rmp = RegisteredModelRegexPermissionEntity(id_=1, regex="new-.*", priority=2, user_id=2, permission="MANAGE")
        mock_store.update_registered_model_regex_permission.return_value = rmp
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/registered-models-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 200

    def test_update_invalid_id(self, authenticated_client, mock_store):
        """Test updating with invalid (non-integer) pattern ID."""
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/registered-models-patterns/abc",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 400

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_registered_model_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/registered-models-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting registered model regex permission."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/registered-models-patterns/1")
        assert resp.status_code == 200

    def test_delete_invalid_id(self, authenticated_client, mock_store):
        """Test deleting with invalid (non-integer) pattern ID."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/registered-models-patterns/abc")
        assert resp.status_code == 400

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_registered_model_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/registered-models-patterns/1")
        assert resp.status_code == 500


# ========================================================================================
# USER PROMPT PERMISSIONS (CRUD - not duplicating list tests from test_user_permissions.py)
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_model_manage")
class TestUserPromptCRUD:
    """Tests for create/update/delete user prompt permissions."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating prompt permission for a user."""
        resp = authenticated_client.post(f"{USER_BASE}/user@example.com/prompts/my-prompt", json={"permission": "READ"})
        assert resp.status_code == 201
        mock_store.create_registered_model_permission.assert_called_once()

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_registered_model_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(f"{USER_BASE}/user@example.com/prompts/my-prompt", json={"permission": "READ"})
        assert resp.status_code == 500

    def test_update(self, authenticated_client, mock_store):
        """Test updating prompt permission for a user."""
        resp = authenticated_client.patch(f"{USER_BASE}/user@example.com/prompts/my-prompt", json={"permission": "EDIT"})
        assert resp.status_code == 200

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting prompt permission for a user."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/prompts/my-prompt")
        assert resp.status_code == 200

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_registered_model_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/prompts/my-prompt")
        assert resp.status_code == 500


# ========================================================================================
# USER PROMPT PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserPromptPatterns:
    """Tests for user prompt regex/pattern permission CRUD."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating prompt regex permission."""
        resp = authenticated_client.post(
            f"{USER_BASE}/user@example.com/prompts-patterns",
            json={"regex": "prompt-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 201
        mock_store.create_prompt_regex_permission.assert_called_once()

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_prompt_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(
            f"{USER_BASE}/user@example.com/prompts-patterns",
            json={"regex": "prompt-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 500

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific prompt regex permission."""
        rmp = RegisteredModelRegexPermissionEntity(id_=1, regex="prompt-.*", priority=1, user_id=2, permission="READ", prompt=True)
        mock_store.get_prompt_regex_permission.return_value = rmp
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/prompts-patterns/1")
        assert resp.status_code == 200

    def test_get_invalid_id(self, authenticated_client, mock_store):
        """Test getting with invalid (non-integer) pattern ID."""
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/prompts-patterns/abc")
        assert resp.status_code == 400

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test getting non-existent pattern."""
        mock_store.get_prompt_regex_permission.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/prompts-patterns/1")
        assert resp.status_code == 404

    def test_update(self, authenticated_client, mock_store):
        """Test updating prompt regex permission."""
        rmp = RegisteredModelRegexPermissionEntity(id_=1, regex="new-.*", priority=2, user_id=2, permission="MANAGE", prompt=True)
        mock_store.update_prompt_regex_permission.return_value = rmp
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/prompts-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 200

    def test_update_invalid_id(self, authenticated_client, mock_store):
        """Test updating with invalid (non-integer) pattern ID."""
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/prompts-patterns/abc",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 400

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_prompt_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/prompts-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting prompt regex permission."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/prompts-patterns/1")
        assert resp.status_code == 200

    def test_delete_invalid_id(self, authenticated_client, mock_store):
        """Test deleting with invalid (non-integer) pattern ID."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/prompts-patterns/abc")
        assert resp.status_code == 400

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_prompt_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/prompts-patterns/1")
        assert resp.status_code == 500


# ========================================================================================
# USER SCORER PERMISSIONS (CRUD)
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_experiment_manage")
class TestUserScorerCRUD:
    """Tests for create/get/update/delete user scorer permissions."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating scorer permission for a user."""
        sp = MagicMock()
        sp.to_json.return_value = {"experiment_id": "1", "scorer_name": "s1", "user_id": 2, "permission": "READ"}
        mock_store.create_scorer_permission.return_value = sp
        resp = authenticated_client.post(f"{USER_BASE}/user@example.com/scorers/1/s1", json={"permission": "READ"})
        assert resp.status_code == 201

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_scorer_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(f"{USER_BASE}/user@example.com/scorers/1/s1", json={"permission": "READ"})
        assert resp.status_code == 500

    def test_get(self, authenticated_client, mock_store):
        """Test getting scorer permission for a user."""
        sp = MagicMock()
        sp.to_json.return_value = {"experiment_id": "1", "scorer_name": "s1", "user_id": 2, "permission": "READ"}
        mock_store.get_scorer_permission.return_value = sp
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/scorers/1/s1")
        assert resp.status_code == 200

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test getting non-existent scorer permission."""
        mock_store.get_scorer_permission.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/scorers/1/s1")
        assert resp.status_code == 404

    def test_update(self, authenticated_client, mock_store):
        """Test updating scorer permission for a user."""
        resp = authenticated_client.patch(f"{USER_BASE}/user@example.com/scorers/1/s1", json={"permission": "EDIT"})
        assert resp.status_code == 200

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_scorer_permission.side_effect = Exception("DB error")
        resp = authenticated_client.patch(f"{USER_BASE}/user@example.com/scorers/1/s1", json={"permission": "EDIT"})
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting scorer permission for a user."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/scorers/1/s1")
        assert resp.status_code == 200
        mock_store.delete_scorer_permission.assert_called_once()

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_scorer_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/scorers/1/s1")
        assert resp.status_code == 500


# ========================================================================================
# USER SCORER PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestUserScorerPatterns:
    """Tests for user scorer regex/pattern permission CRUD."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating scorer regex permission."""
        sp = MagicMock()
        sp.to_json.return_value = {"id": 1, "regex": ".*", "priority": 1, "user_id": 2, "permission": "READ"}
        mock_store.create_scorer_regex_permission.return_value = sp
        resp = authenticated_client.post(
            f"{USER_BASE}/user@example.com/scorer-patterns",
            json={"regex": ".*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 201

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_scorer_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(
            f"{USER_BASE}/user@example.com/scorer-patterns",
            json={"regex": ".*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 500

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific scorer regex permission."""
        sp = MagicMock()
        sp.to_json.return_value = {"id": 1, "regex": ".*", "priority": 1, "user_id": 2, "permission": "READ"}
        mock_store.get_scorer_regex_permission.return_value = sp
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/scorer-patterns/1")
        assert resp.status_code == 200

    def test_get_not_found(self, authenticated_client, mock_store):
        """Test getting non-existent pattern."""
        mock_store.get_scorer_regex_permission.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{USER_BASE}/user@example.com/scorer-patterns/1")
        assert resp.status_code == 404

    def test_update(self, authenticated_client, mock_store):
        """Test updating scorer regex permission."""
        sp = MagicMock()
        sp.to_json.return_value = {"id": 1, "regex": "new-.*", "priority": 2, "user_id": 2, "permission": "MANAGE"}
        mock_store.update_scorer_regex_permission.return_value = sp
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/scorer-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 200

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_scorer_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.patch(
            f"{USER_BASE}/user@example.com/scorer-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting scorer regex permission."""
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/scorer-patterns/1")
        assert resp.status_code == 200
        mock_store.delete_scorer_regex_permission.assert_called_once()

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_scorer_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{USER_BASE}/user@example.com/scorer-patterns/1")
        assert resp.status_code == 500
