"""Tests for FastAPI dependency functions — gateway permission checks."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI

from mlflow_oidc_auth.dependencies import (
    check_gateway_endpoint_manage_permission,
    check_gateway_model_definition_manage_permission,
    check_gateway_secret_manage_permission,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with routes guarded by each gateway dependency."""
    app = FastAPI()

    @app.get("/test/endpoint/{name}")
    async def ep_route(result=None):  # noqa: D401
        return {"ok": True}

    @app.get("/test/secret/{name}")
    async def secret_route(result=None):  # noqa: D401
        return {"ok": True}

    @app.get("/test/model-def/{name}")
    async def model_def_route(result=None):  # noqa: D401
        return {"ok": True}

    return app


# ---------------------------------------------------------------------------
# check_gateway_endpoint_manage_permission
# ---------------------------------------------------------------------------


class TestCheckGatewayEndpointManagePermission:
    """Tests for check_gateway_endpoint_manage_permission dependency."""

    @pytest.mark.anyio
    async def test_allows_admin(self) -> None:
        """Admin should be allowed regardless of can_manage result."""
        with patch("mlflow_oidc_auth.dependencies.get_username", new_callable=AsyncMock, return_value="admin@example.com"):
            with patch("mlflow_oidc_auth.dependencies.get_is_admin", new_callable=AsyncMock, return_value=True):
                with patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint", return_value=False):
                    result = await check_gateway_endpoint_manage_permission(
                        name="ep-1",
                        current_username="admin@example.com",
                        is_admin=True,
                    )

        assert result is None

    @pytest.mark.anyio
    async def test_allows_user_with_manage_permission(self) -> None:
        """Non-admin with manage permission should be allowed."""
        with patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint", return_value=True):
            result = await check_gateway_endpoint_manage_permission(
                name="ep-1",
                current_username="user@example.com",
                is_admin=False,
            )

        assert result is None

    @pytest.mark.anyio
    async def test_denies_user_without_manage_permission(self) -> None:
        """Non-admin without manage permission should be denied."""
        from fastapi import HTTPException

        with patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_endpoint", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await check_gateway_endpoint_manage_permission(
                    name="ep-1",
                    current_username="user@example.com",
                    is_admin=False,
                )

        assert exc_info.value.status_code == 403
        assert "endpoint" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# check_gateway_secret_manage_permission
# ---------------------------------------------------------------------------


class TestCheckGatewaySecretManagePermission:
    """Tests for check_gateway_secret_manage_permission dependency."""

    @pytest.mark.anyio
    async def test_allows_admin(self) -> None:
        """Admin should be allowed."""
        result = await check_gateway_secret_manage_permission(
            name="secret-1",
            current_username="admin@example.com",
            is_admin=True,
        )
        assert result is None

    @pytest.mark.anyio
    async def test_allows_user_with_manage_permission(self) -> None:
        """Non-admin with manage permission should be allowed."""
        with patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_secret", return_value=True):
            result = await check_gateway_secret_manage_permission(
                name="secret-1",
                current_username="user@example.com",
                is_admin=False,
            )

        assert result is None

    @pytest.mark.anyio
    async def test_denies_user_without_manage_permission(self) -> None:
        """Non-admin without manage permission should be denied."""
        from fastapi import HTTPException

        with patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_secret", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await check_gateway_secret_manage_permission(
                    name="secret-1",
                    current_username="user@example.com",
                    is_admin=False,
                )

        assert exc_info.value.status_code == 403
        assert "secret" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# check_gateway_model_definition_manage_permission
# ---------------------------------------------------------------------------


class TestCheckGatewayModelDefinitionManagePermission:
    """Tests for check_gateway_model_definition_manage_permission dependency."""

    @pytest.mark.anyio
    async def test_allows_admin(self) -> None:
        """Admin should be allowed."""
        result = await check_gateway_model_definition_manage_permission(
            name="model-1",
            current_username="admin@example.com",
            is_admin=True,
        )
        assert result is None

    @pytest.mark.anyio
    async def test_allows_user_with_manage_permission(self) -> None:
        """Non-admin with manage permission should be allowed."""
        with patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_model_definition", return_value=True):
            result = await check_gateway_model_definition_manage_permission(
                name="model-1",
                current_username="user@example.com",
                is_admin=False,
            )

        assert result is None

    @pytest.mark.anyio
    async def test_denies_user_without_manage_permission(self) -> None:
        """Non-admin without manage permission should be denied."""
        from fastapi import HTTPException

        with patch("mlflow_oidc_auth.utils.permissions.can_manage_gateway_model_definition", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await check_gateway_model_definition_manage_permission(
                    name="model-1",
                    current_username="user@example.com",
                    is_admin=False,
                )

        assert exc_info.value.status_code == 403
        assert "model definition" in exc_info.value.detail.lower()
