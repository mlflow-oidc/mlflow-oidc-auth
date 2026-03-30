"""Tests for workspace CRUD Pydantic models.

Verifies name validation, field constraints, reserved-name rejection, and
default values for WorkspaceCrudCreateRequest, WorkspaceCrudUpdateRequest,
and WorkspaceCrudResponse.
"""

import pytest
from pydantic import ValidationError


class TestWorkspaceCrudPydanticModels:
    """Test Pydantic request/response models for workspace CRUD."""

    def test_create_request_valid_name(self):
        """Valid DNS-safe name is accepted."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        req = WorkspaceCrudCreateRequest(name="my-workspace", description="A workspace")
        assert req.name == "my-workspace"
        assert req.description == "A workspace"
        assert req.default_artifact_root is None

    def test_create_request_valid_name_numeric(self):
        """Purely numeric name is DNS-safe and accepted."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        req = WorkspaceCrudCreateRequest(name="ws01")
        assert req.name == "ws01"

    def test_create_request_rejects_uppercase(self):
        """Uppercase letters are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="MyWorkspace")

    def test_create_request_rejects_too_long(self):
        """Names > 63 characters are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="a" * 64)

    def test_create_request_rejects_too_short(self):
        """Names < 2 characters are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="a")

    def test_create_request_rejects_reserved_name(self):
        """Reserved names ('workspaces', 'api', etc.) are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        for reserved in ["workspaces", "api", "ajax-api", "static-files"]:
            with pytest.raises(ValidationError, match="reserved"):
                WorkspaceCrudCreateRequest(name=reserved)

    def test_create_request_rejects_leading_hyphen(self):
        """Leading hyphen is rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="-workspace")

    def test_create_request_rejects_trailing_hyphen(self):
        """Trailing hyphen is rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="workspace-")

    def test_create_request_rejects_consecutive_hyphens(self):
        """Consecutive hyphens are rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="work--space")

    def test_create_request_default_description(self):
        """Description defaults to empty string."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        req = WorkspaceCrudCreateRequest(name="ws")
        assert req.description == ""

    def test_create_request_with_artifact_root(self):
        """Create request accepts optional default_artifact_root."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        req = WorkspaceCrudCreateRequest(
            name="my-ws",
            description="desc",
            default_artifact_root="s3://team-a-artifacts",
        )
        assert req.default_artifact_root == "s3://team-a-artifacts"

    def test_create_request_rejects_too_long_artifact_root(self):
        """Artifact root > 1024 characters is rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudCreateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudCreateRequest(name="my-ws", default_artifact_root="s3://" + "a" * 1020)

    def test_update_request_valid(self):
        """Update request accepts valid description."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudUpdateRequest

        req = WorkspaceCrudUpdateRequest(description="Updated desc")
        assert req.description == "Updated desc"
        assert req.default_artifact_root is None

    def test_update_request_with_artifact_root(self):
        """Update request accepts optional default_artifact_root."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudUpdateRequest

        req = WorkspaceCrudUpdateRequest(
            description="Updated",
            default_artifact_root="gs://my-bucket/artifacts",
        )
        assert req.default_artifact_root == "gs://my-bucket/artifacts"

    def test_update_request_rejects_too_long_artifact_root(self):
        """Artifact root > 1024 characters is rejected on update."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudUpdateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudUpdateRequest(
                description="ok",
                default_artifact_root="s3://" + "a" * 1020,
            )

    def test_update_request_rejects_too_long_description(self):
        """Description > 500 characters is rejected."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudUpdateRequest

        with pytest.raises(ValidationError):
            WorkspaceCrudUpdateRequest(description="x" * 501)

    def test_response_model_fields(self):
        """Response model has name, description, and default_artifact_root fields."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudResponse

        resp = WorkspaceCrudResponse(
            name="ws1",
            description="desc",
            default_artifact_root="s3://bucket",
        )
        assert resp.name == "ws1"
        assert resp.description == "desc"
        assert resp.default_artifact_root == "s3://bucket"

    def test_response_model_default_description(self):
        """Response model description defaults to empty string, artifact root to None."""
        from mlflow_oidc_auth.models.workspace import WorkspaceCrudResponse

        resp = WorkspaceCrudResponse(name="ws1")
        assert resp.description == ""
        assert resp.default_artifact_root is None
