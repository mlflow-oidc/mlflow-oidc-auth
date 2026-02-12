"""Tests for non-gateway CRUD endpoints in group_permissions router.

Covers experiments, registered models, prompts, and their pattern variants,
plus group listing and group-user listing.
"""

from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.dependencies import check_admin_permission, check_experiment_manage_permission


GROUP_BASE = "/api/2.0/mlflow/permissions/groups"

# Module path where effective_* functions are imported in the router
_GP = "mlflow_oidc_auth.routers.group_permissions"


def _mock_eff_perm():
    """Return a mock effective permission result where can_manage=True."""
    result = MagicMock()
    result.permission.can_manage = True
    return result


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


def _make_regex_pattern():
    """Create a mock regex pattern with to_json support."""
    perm = MagicMock()
    perm.to_json.return_value = {"id": 1, "regex": ".*", "priority": 1, "group_id": 10, "permission": "READ"}
    return perm


def _make_model_regex_pattern():
    """Create a mock registered model regex pattern with to_json support."""
    perm = MagicMock()
    perm.to_json.return_value = {"id": 1, "regex": ".*", "priority": 1, "group_id": 10, "permission": "READ", "prompt": False}
    return perm


def _make_prompt_regex_pattern():
    """Create a mock prompt regex pattern with to_json support."""
    perm = MagicMock()
    perm.to_json.return_value = {"id": 1, "regex": ".*", "priority": 1, "group_id": 10, "permission": "READ", "prompt": True}
    return perm


# ========================================================================================
# GROUP LISTING
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session")
class TestListGroups:
    """Tests for list_groups endpoint."""

    def test_list_groups_success(self, authenticated_client, mock_store):
        """Test listing all groups."""
        mock_store.get_groups.return_value = ["devs", "admins"]
        with patch(f"{_GP}.store", mock_store):
            resp = authenticated_client.get(GROUP_BASE)
        assert resp.status_code == 200

    def test_list_groups_error(self, authenticated_client, mock_store):
        """Test error handling when listing groups fails."""
        mock_store.get_groups.side_effect = Exception("DB error")
        with patch(f"{_GP}.store", mock_store):
            resp = authenticated_client.get(GROUP_BASE)
        assert resp.status_code == 500


# ========================================================================================
# GROUP USERS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupUsers:
    """Tests for get_group_users endpoint."""

    def test_get_group_users_success(self, authenticated_client, mock_store):
        """Test getting users in a group."""
        user = MagicMock()
        user.username = "alice@example.com"
        user.is_admin = False
        mock_store.get_group_users.return_value = [user]
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/users")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["username"] == "alice@example.com"

    def test_get_group_users_not_found(self, authenticated_client, mock_store):
        """Test error when group not found."""
        mock_store.get_group_users.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{GROUP_BASE}/missing/users")
        assert resp.status_code == 404


# ========================================================================================
# GROUP EXPERIMENT PERMISSIONS (LIST / CRUD)
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session")
class TestGroupExperimentList:
    """Tests for get_group_experiments (list) endpoint."""

    def test_list_experiments_as_admin(self, admin_client, mock_store):
        """Admin sees all group experiments."""
        exp_perm = MagicMock()
        exp_perm.experiment_id = "123"
        exp_perm.permission = "MANAGE"
        mock_store.get_group_experiments.return_value = [exp_perm]

        mock_tracking = MagicMock()
        mock_experiment = MagicMock()
        mock_experiment.name = "Test Experiment"
        mock_tracking.get_experiment.return_value = mock_experiment

        with patch(f"{_GP}._get_tracking_store", return_value=mock_tracking):
            resp = admin_client.get(f"{GROUP_BASE}/devs/experiments")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == "123"
        assert body[0]["name"] == "Test Experiment"
        assert body[0]["permission"] == "MANAGE"

    def test_list_experiments_error(self, admin_client, mock_store):
        """Test error handling."""
        mock_store.get_group_experiments.side_effect = Exception("DB error")
        with patch(f"{_GP}._get_tracking_store", return_value=MagicMock()):
            resp = admin_client.get(f"{GROUP_BASE}/devs/experiments")
        assert resp.status_code == 500


@pytest.mark.usefixtures("authenticated_session", "override_experiment_manage")
class TestGroupExperimentCRUD:
    """Tests for create/update/delete group experiment permissions."""

    def test_create(self, authenticated_client, mock_store):
        """Test creating experiment permission for a group."""
        resp = authenticated_client.post(f"{GROUP_BASE}/devs/experiments/exp-1", json={"permission": "READ"})
        assert resp.status_code == 201
        assert "created" in resp.json()["message"].lower()
        mock_store.create_group_experiment_permission.assert_called_once()

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_group_experiment_permission.side_effect = Exception("Duplicate")
        resp = authenticated_client.post(f"{GROUP_BASE}/devs/experiments/exp-1", json={"permission": "READ"})
        assert resp.status_code == 500

    def test_update(self, authenticated_client, mock_store):
        """Test updating experiment permission for a group."""
        resp = authenticated_client.patch(f"{GROUP_BASE}/devs/experiments/exp-1", json={"permission": "EDIT"})
        assert resp.status_code == 200
        assert "updated" in resp.json()["message"].lower()

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_group_experiment_permission.side_effect = Exception("Not found")
        resp = authenticated_client.patch(f"{GROUP_BASE}/devs/experiments/exp-1", json={"permission": "EDIT"})
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting experiment permission for a group."""
        resp = authenticated_client.delete(f"{GROUP_BASE}/devs/experiments/exp-1")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_group_experiment_permission.side_effect = Exception("Not found")
        resp = authenticated_client.delete(f"{GROUP_BASE}/devs/experiments/exp-1")
        assert resp.status_code == 500


# ========================================================================================
# GROUP REGISTERED MODEL PERMISSIONS (LIST / CRUD)
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session")
class TestGroupRegisteredModelList:
    """Tests for get_group_registered_models (list) endpoint."""

    def test_list_models_as_admin(self, admin_client, mock_store):
        """Admin sees all group models."""
        model_perm = MagicMock()
        model_perm.name = "my-model"
        model_perm.permission = "READ"
        mock_store.get_group_models.return_value = [model_perm]

        resp = admin_client.get(f"{GROUP_BASE}/devs/registered-models")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "my-model"

    def test_list_models_non_admin_with_manage(self, authenticated_client, mock_store):
        """Non-admin user with manage permission can see models."""
        model_perm = MagicMock()
        model_perm.name = "my-model"
        model_perm.permission = "READ"
        mock_store.get_group_models.return_value = [model_perm]

        with patch(f"{_GP}.effective_registered_model_permission", return_value=_mock_eff_perm()):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/registered-models")
        assert resp.status_code == 200

    def test_list_models_error(self, admin_client, mock_store):
        """Test error handling."""
        mock_store.get_group_models.side_effect = Exception("DB error")
        resp = admin_client.get(f"{GROUP_BASE}/devs/registered-models")
        assert resp.status_code == 500


@pytest.mark.usefixtures("authenticated_session")
class TestGroupRegisteredModelCRUD:
    """Tests for create/update/delete group registered model permissions."""

    def test_create_as_admin(self, admin_client, mock_store):
        """Admin can create registered model permission."""
        resp = admin_client.post(f"{GROUP_BASE}/devs/registered-models/my-model", json={"permission": "READ"})
        assert resp.status_code == 201
        mock_store.create_group_model_permission.assert_called_once()

    def test_create_non_admin_with_manage(self, authenticated_client, mock_store):
        """Non-admin with manage permission can create."""
        with patch(f"{_GP}.effective_registered_model_permission", return_value=_mock_eff_perm()):
            resp = authenticated_client.post(f"{GROUP_BASE}/devs/registered-models/my-model", json={"permission": "READ"})
        assert resp.status_code == 201

    def test_create_non_admin_no_manage(self, authenticated_client, mock_store):
        """Non-admin without manage permission gets 403."""
        no_perm = MagicMock()
        no_perm.permission.can_manage = False
        with patch(f"{_GP}.effective_registered_model_permission", return_value=no_perm):
            resp = authenticated_client.post(f"{GROUP_BASE}/devs/registered-models/my-model", json={"permission": "READ"})
        assert resp.status_code == 403

    def test_create_error(self, admin_client, mock_store):
        """Test error handling for create."""
        mock_store.create_group_model_permission.side_effect = Exception("DB error")
        resp = admin_client.post(f"{GROUP_BASE}/devs/registered-models/my-model", json={"permission": "READ"})
        assert resp.status_code == 500

    def test_update_as_admin(self, admin_client, mock_store):
        """Admin can update registered model permission."""
        resp = admin_client.patch(f"{GROUP_BASE}/devs/registered-models/my-model", json={"permission": "EDIT"})
        assert resp.status_code == 200

    def test_update_error(self, admin_client, mock_store):
        """Test error handling for update."""
        mock_store.update_group_model_permission.side_effect = Exception("DB error")
        resp = admin_client.patch(f"{GROUP_BASE}/devs/registered-models/my-model", json={"permission": "EDIT"})
        assert resp.status_code == 500

    def test_delete_as_admin(self, admin_client, mock_store):
        """Admin can delete registered model permission."""
        resp = admin_client.delete(f"{GROUP_BASE}/devs/registered-models/my-model")
        assert resp.status_code == 200

    def test_delete_non_admin_no_manage(self, authenticated_client, mock_store):
        """Non-admin without manage permission gets 403."""
        no_perm = MagicMock()
        no_perm.permission.can_manage = False
        with patch(f"{_GP}.effective_registered_model_permission", return_value=no_perm):
            resp = authenticated_client.delete(f"{GROUP_BASE}/devs/registered-models/my-model")
        assert resp.status_code == 403

    def test_delete_error(self, admin_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_group_model_permission.side_effect = Exception("DB error")
        resp = admin_client.delete(f"{GROUP_BASE}/devs/registered-models/my-model")
        assert resp.status_code == 500


# ========================================================================================
# GROUP PROMPT PERMISSIONS (LIST / CRUD)
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session")
class TestGroupPromptList:
    """Tests for get_group_prompts (list) endpoint."""

    def test_list_prompts_as_admin(self, admin_client, mock_store):
        """Admin sees all group prompts."""
        prompt_perm = MagicMock()
        prompt_perm.name = "my-prompt"
        prompt_perm.permission = "READ"
        mock_store.get_group_prompts.return_value = [prompt_perm]

        resp = admin_client.get(f"{GROUP_BASE}/devs/prompts")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "my-prompt"

    def test_list_prompts_non_admin_with_manage(self, authenticated_client, mock_store):
        """Non-admin with manage permission can see prompts."""
        prompt_perm = MagicMock()
        prompt_perm.name = "my-prompt"
        prompt_perm.permission = "READ"
        mock_store.get_group_prompts.return_value = [prompt_perm]

        with patch(f"{_GP}.effective_prompt_permission", return_value=_mock_eff_perm()):
            resp = authenticated_client.get(f"{GROUP_BASE}/devs/prompts")
        assert resp.status_code == 200

    def test_list_prompts_error(self, admin_client, mock_store):
        """Test error handling."""
        mock_store.get_group_prompts.side_effect = Exception("DB error")
        resp = admin_client.get(f"{GROUP_BASE}/devs/prompts")
        assert resp.status_code == 500


@pytest.mark.usefixtures("authenticated_session")
class TestGroupPromptCRUD:
    """Tests for create/update/delete group prompt permissions."""

    def test_create_as_admin(self, admin_client, mock_store):
        """Admin can create prompt permission."""
        resp = admin_client.post(f"{GROUP_BASE}/devs/prompts/my-prompt", json={"permission": "READ"})
        assert resp.status_code == 201
        mock_store.create_group_prompt_permission.assert_called_once()

    def test_create_non_admin_with_manage(self, authenticated_client, mock_store):
        """Non-admin with manage permission can create."""
        with patch(f"{_GP}.effective_prompt_permission", return_value=_mock_eff_perm()):
            resp = authenticated_client.post(f"{GROUP_BASE}/devs/prompts/my-prompt", json={"permission": "READ"})
        assert resp.status_code == 201

    def test_create_non_admin_no_manage(self, authenticated_client, mock_store):
        """Non-admin without manage permission gets 403."""
        no_perm = MagicMock()
        no_perm.permission.can_manage = False
        with patch(f"{_GP}.effective_prompt_permission", return_value=no_perm):
            resp = authenticated_client.post(f"{GROUP_BASE}/devs/prompts/my-prompt", json={"permission": "READ"})
        assert resp.status_code == 403

    def test_create_error(self, admin_client, mock_store):
        """Test error handling for create."""
        mock_store.create_group_prompt_permission.side_effect = Exception("DB error")
        resp = admin_client.post(f"{GROUP_BASE}/devs/prompts/my-prompt", json={"permission": "READ"})
        assert resp.status_code == 500

    def test_update_as_admin(self, admin_client, mock_store):
        """Admin can update prompt permission."""
        resp = admin_client.patch(f"{GROUP_BASE}/devs/prompts/my-prompt", json={"permission": "EDIT"})
        assert resp.status_code == 200

    def test_update_non_admin_no_manage(self, authenticated_client, mock_store):
        """Non-admin without manage permission gets 403."""
        no_perm = MagicMock()
        no_perm.permission.can_manage = False
        with patch(f"{_GP}.effective_prompt_permission", return_value=no_perm):
            resp = authenticated_client.patch(f"{GROUP_BASE}/devs/prompts/my-prompt", json={"permission": "EDIT"})
        assert resp.status_code == 403

    def test_update_error(self, admin_client, mock_store):
        """Test error handling for update."""
        mock_store.update_group_prompt_permission.side_effect = Exception("DB error")
        resp = admin_client.patch(f"{GROUP_BASE}/devs/prompts/my-prompt", json={"permission": "EDIT"})
        assert resp.status_code == 500

    def test_delete_as_admin(self, admin_client, mock_store):
        """Admin can delete prompt permission."""
        resp = admin_client.delete(f"{GROUP_BASE}/devs/prompts/my-prompt")
        assert resp.status_code == 200

    def test_delete_non_admin_no_manage(self, authenticated_client, mock_store):
        """Non-admin without manage permission gets 403."""
        no_perm = MagicMock()
        no_perm.permission.can_manage = False
        with patch(f"{_GP}.effective_prompt_permission", return_value=no_perm):
            resp = authenticated_client.delete(f"{GROUP_BASE}/devs/prompts/my-prompt")
        assert resp.status_code == 403

    def test_delete_error(self, admin_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_group_prompt_permission.side_effect = Exception("DB error")
        resp = admin_client.delete(f"{GROUP_BASE}/devs/prompts/my-prompt")
        assert resp.status_code == 500


# ========================================================================================
# GROUP EXPERIMENT PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupExperimentPatterns:
    """Tests for group experiment regex/pattern permission CRUD."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing group experiment regex permissions."""
        mock_store.list_group_experiment_regex_permissions.return_value = [_make_regex_pattern()]
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/experiment-patterns")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["regex"] == ".*"

    def test_list_without_to_json(self, authenticated_client, mock_store):
        """Test listing with pattern that has no to_json (fallback path)."""
        perm = MagicMock(spec=[])  # no to_json
        perm.id = 1
        perm.regex = ".*"
        perm.priority = 1
        perm.group_id = 10
        perm.permission = "READ"
        mock_store.list_group_experiment_regex_permissions.return_value = [perm]
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/experiment-patterns")
        assert resp.status_code == 200

    def test_list_error(self, authenticated_client, mock_store):
        """Test error handling for list."""
        mock_store.list_group_experiment_regex_permissions.side_effect = Exception("DB error")
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/experiment-patterns")
        assert resp.status_code == 500

    def test_create(self, authenticated_client, mock_store):
        """Test creating experiment regex permission."""
        resp = authenticated_client.post(
            f"{GROUP_BASE}/devs/experiment-patterns",
            json={"regex": "exp-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 201
        mock_store.create_group_experiment_regex_permission.assert_called_once()

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_group_experiment_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(
            f"{GROUP_BASE}/devs/experiment-patterns",
            json={"regex": "exp-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 500

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific experiment regex permission."""
        mock_store.get_group_experiment_regex_permission.return_value = _make_regex_pattern()
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/experiment-patterns/1")
        assert resp.status_code == 200

    def test_get_without_to_json(self, authenticated_client, mock_store):
        """Test getting with pattern that has no to_json (fallback path)."""
        perm = MagicMock(spec=[])
        perm.id = 1
        perm.regex = ".*"
        perm.priority = 1
        perm.group_id = 10
        perm.permission = "READ"
        mock_store.get_group_experiment_regex_permission.return_value = perm
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/experiment-patterns/1")
        assert resp.status_code == 200

    def test_get_error(self, authenticated_client, mock_store):
        """Test error handling for get."""
        mock_store.get_group_experiment_regex_permission.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/experiment-patterns/1")
        assert resp.status_code == 500

    def test_update(self, authenticated_client, mock_store):
        """Test updating experiment regex permission."""
        resp = authenticated_client.patch(
            f"{GROUP_BASE}/devs/experiment-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 200
        mock_store.update_group_experiment_regex_permission.assert_called_once()

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_group_experiment_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.patch(
            f"{GROUP_BASE}/devs/experiment-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting experiment regex permission."""
        resp = authenticated_client.delete(f"{GROUP_BASE}/devs/experiment-patterns/1")
        assert resp.status_code == 200
        mock_store.delete_group_experiment_regex_permission.assert_called_once()

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_group_experiment_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{GROUP_BASE}/devs/experiment-patterns/1")
        assert resp.status_code == 500


# ========================================================================================
# GROUP REGISTERED MODEL PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupRegisteredModelPatterns:
    """Tests for group registered model regex/pattern permission CRUD."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing registered model regex permissions."""
        mock_store.list_group_registered_model_regex_permissions.return_value = [_make_model_regex_pattern()]
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/registered-models-patterns")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1

    def test_list_without_to_json(self, authenticated_client, mock_store):
        """Test listing with pattern that has no to_json (fallback path)."""
        perm = MagicMock(spec=[])
        perm.id = 1
        perm.regex = ".*"
        perm.priority = 1
        perm.group_id = 10
        perm.permission = "READ"
        perm.prompt = False
        mock_store.list_group_registered_model_regex_permissions.return_value = [perm]
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/registered-models-patterns")
        assert resp.status_code == 200

    def test_list_error(self, authenticated_client, mock_store):
        """Test error handling for list."""
        mock_store.list_group_registered_model_regex_permissions.side_effect = Exception("DB error")
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/registered-models-patterns")
        assert resp.status_code == 500

    def test_create(self, authenticated_client, mock_store):
        """Test creating registered model regex permission."""
        resp = authenticated_client.post(
            f"{GROUP_BASE}/devs/registered-models-patterns",
            json={"regex": "model-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 201

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_group_registered_model_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(
            f"{GROUP_BASE}/devs/registered-models-patterns",
            json={"regex": "model-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 500

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific registered model regex permission."""
        mock_store.get_group_registered_model_regex_permission.return_value = _make_model_regex_pattern()
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/registered-models-patterns/1")
        assert resp.status_code == 200

    def test_get_without_to_json(self, authenticated_client, mock_store):
        """Test getting with pattern that has no to_json (fallback path)."""
        perm = MagicMock(spec=[])
        perm.id = 1
        perm.regex = ".*"
        perm.priority = 1
        perm.group_id = 10
        perm.permission = "READ"
        perm.prompt = False
        mock_store.get_group_registered_model_regex_permission.return_value = perm
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/registered-models-patterns/1")
        assert resp.status_code == 200

    def test_get_error(self, authenticated_client, mock_store):
        """Test error handling for get."""
        mock_store.get_group_registered_model_regex_permission.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/registered-models-patterns/1")
        assert resp.status_code == 500

    def test_update(self, authenticated_client, mock_store):
        """Test updating registered model regex permission."""
        resp = authenticated_client.patch(
            f"{GROUP_BASE}/devs/registered-models-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 200

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_group_registered_model_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.patch(
            f"{GROUP_BASE}/devs/registered-models-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting registered model regex permission."""
        resp = authenticated_client.delete(f"{GROUP_BASE}/devs/registered-models-patterns/1")
        assert resp.status_code == 200

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_group_registered_model_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{GROUP_BASE}/devs/registered-models-patterns/1")
        assert resp.status_code == 500


# ========================================================================================
# GROUP PROMPT PATTERN PERMISSIONS
# ========================================================================================


@pytest.mark.usefixtures("authenticated_session", "override_admin")
class TestGroupPromptPatterns:
    """Tests for group prompt regex/pattern permission CRUD."""

    def test_list(self, authenticated_client, mock_store):
        """Test listing prompt regex permissions."""
        mock_store.list_group_prompt_regex_permissions.return_value = [_make_prompt_regex_pattern()]
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/prompts-patterns")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1

    def test_list_without_to_json(self, authenticated_client, mock_store):
        """Test listing with pattern that has no to_json (fallback path)."""
        perm = MagicMock(spec=[])
        perm.id = 1
        perm.regex = ".*"
        perm.priority = 1
        perm.group_id = 10
        perm.permission = "READ"
        perm.prompt = True
        mock_store.list_group_prompt_regex_permissions.return_value = [perm]
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/prompts-patterns")
        assert resp.status_code == 200

    def test_list_error(self, authenticated_client, mock_store):
        """Test error handling for list."""
        mock_store.list_group_prompt_regex_permissions.side_effect = Exception("DB error")
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/prompts-patterns")
        assert resp.status_code == 500

    def test_create(self, authenticated_client, mock_store):
        """Test creating prompt regex permission."""
        resp = authenticated_client.post(
            f"{GROUP_BASE}/devs/prompts-patterns",
            json={"regex": "prompt-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 201

    def test_create_error(self, authenticated_client, mock_store):
        """Test error handling for create."""
        mock_store.create_group_prompt_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.post(
            f"{GROUP_BASE}/devs/prompts-patterns",
            json={"regex": "prompt-.*", "priority": 1, "permission": "READ"},
        )
        assert resp.status_code == 500

    def test_get(self, authenticated_client, mock_store):
        """Test getting a specific prompt regex permission."""
        mock_store.get_group_prompt_regex_permission.return_value = _make_prompt_regex_pattern()
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/prompts-patterns/1")
        assert resp.status_code == 200

    def test_get_error(self, authenticated_client, mock_store):
        """Test error handling for get."""
        mock_store.get_group_prompt_regex_permission.side_effect = Exception("Not found")
        resp = authenticated_client.get(f"{GROUP_BASE}/devs/prompts-patterns/1")
        assert resp.status_code == 500

    def test_update(self, authenticated_client, mock_store):
        """Test updating prompt regex permission."""
        resp = authenticated_client.patch(
            f"{GROUP_BASE}/devs/prompts-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 200

    def test_update_error(self, authenticated_client, mock_store):
        """Test error handling for update."""
        mock_store.update_group_prompt_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.patch(
            f"{GROUP_BASE}/devs/prompts-patterns/1",
            json={"regex": "new-.*", "priority": 2, "permission": "MANAGE"},
        )
        assert resp.status_code == 500

    def test_delete(self, authenticated_client, mock_store):
        """Test deleting prompt regex permission."""
        resp = authenticated_client.delete(f"{GROUP_BASE}/devs/prompts-patterns/1")
        assert resp.status_code == 200

    def test_delete_error(self, authenticated_client, mock_store):
        """Test error handling for delete."""
        mock_store.delete_group_prompt_regex_permission.side_effect = Exception("DB error")
        resp = authenticated_client.delete(f"{GROUP_BASE}/devs/prompts-patterns/1")
        assert resp.status_code == 500
