"""Tests for non-gateway dependency functions — prompt and scorer permission checks.

Covers:
- check_prompt_manage_permission
- check_scorer_manage_permission
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from mlflow_oidc_auth.dependencies import (
    check_prompt_manage_permission,
    check_scorer_manage_permission,
)

# ---------------------------------------------------------------------------
# check_prompt_manage_permission
# ---------------------------------------------------------------------------


class TestCheckPromptManagePermission:
    """Tests for check_prompt_manage_permission dependency."""

    @pytest.mark.anyio
    async def test_allows_admin(self) -> None:
        """Admin should be allowed regardless of can_manage result."""
        result = await check_prompt_manage_permission(
            prompt_name="my-prompt",
            current_username="admin@example.com",
            is_admin=True,
        )
        assert result is None

    @pytest.mark.anyio
    async def test_allows_user_with_manage_permission(self) -> None:
        """Non-admin with manage permission should be allowed."""
        with patch("mlflow_oidc_auth.dependencies.can_manage_registered_model", return_value=True):
            result = await check_prompt_manage_permission(
                prompt_name="my-prompt",
                current_username="user@example.com",
                is_admin=False,
            )
        assert result is None

    @pytest.mark.anyio
    async def test_denies_user_without_manage_permission(self) -> None:
        """Non-admin without manage permission should get 403."""
        with patch("mlflow_oidc_auth.dependencies.can_manage_registered_model", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await check_prompt_manage_permission(
                    prompt_name="locked-prompt",
                    current_username="user@example.com",
                    is_admin=False,
                )
        assert exc_info.value.status_code == 403
        assert "locked-prompt" in exc_info.value.detail


# ---------------------------------------------------------------------------
# check_scorer_manage_permission
# ---------------------------------------------------------------------------


class TestCheckScorerManagePermission:
    """Tests for check_scorer_manage_permission dependency."""

    @pytest.mark.anyio
    async def test_allows_admin_with_query_params(self) -> None:
        """Admin should be allowed when params come from query string."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.query_params = {"experiment_id": "exp-1", "scorer_name": "accuracy"}
        mock_request.path_params = {}

        result = await check_scorer_manage_permission(
            request=mock_request,
            current_username="admin@example.com",
            is_admin=True,
        )
        assert result is None

    @pytest.mark.anyio
    async def test_allows_admin_with_path_params(self) -> None:
        """Admin should be allowed when params come from path."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.query_params = {}
        mock_request.path_params = {"experiment_id": "exp-1", "scorer_name": "accuracy"}

        result = await check_scorer_manage_permission(
            request=mock_request,
            current_username="admin@example.com",
            is_admin=True,
        )
        assert result is None

    @pytest.mark.anyio
    async def test_allows_user_with_manage_permission(self) -> None:
        """Non-admin with manage permission should be allowed."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.query_params = {"experiment_id": "exp-1", "scorer_name": "accuracy"}
        mock_request.path_params = {}

        with patch("mlflow_oidc_auth.dependencies.can_manage_scorer", return_value=True):
            result = await check_scorer_manage_permission(
                request=mock_request,
                current_username="user@example.com",
                is_admin=False,
            )
        assert result is None

    @pytest.mark.anyio
    async def test_denies_user_without_manage_permission(self) -> None:
        """Non-admin without manage permission should get 403."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.query_params = {"experiment_id": "exp-1", "scorer_name": "accuracy"}
        mock_request.path_params = {}

        with patch("mlflow_oidc_auth.dependencies.can_manage_scorer", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await check_scorer_manage_permission(
                    request=mock_request,
                    current_username="user@example.com",
                    is_admin=False,
                )
        assert exc_info.value.status_code == 403
        assert "accuracy" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_reads_params_from_post_body(self) -> None:
        """POST request should read params from JSON body."""
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.query_params = {}
        mock_request.path_params = {}
        mock_request.json = AsyncMock(return_value={"experiment_id": "exp-1", "scorer_name": "f1_score"})

        result = await check_scorer_manage_permission(
            request=mock_request,
            current_username="admin@example.com",
            is_admin=True,
        )
        assert result is None

    @pytest.mark.anyio
    async def test_post_body_fallback_on_json_error(self) -> None:
        """POST with invalid JSON should fall back to query/path params."""
        mock_request = MagicMock()
        mock_request.method = "DELETE"
        mock_request.query_params = {"experiment_id": "exp-1", "scorer_name": "precision"}
        mock_request.path_params = {}
        mock_request.json = AsyncMock(side_effect=Exception("no JSON"))

        result = await check_scorer_manage_permission(
            request=mock_request,
            current_username="admin@example.com",
            is_admin=True,
        )
        assert result is None

    @pytest.mark.anyio
    async def test_raises_400_when_missing_experiment_id(self) -> None:
        """Should raise 400 when experiment_id is missing."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.query_params = {"scorer_name": "accuracy"}
        mock_request.path_params = {}

        with pytest.raises(HTTPException) as exc_info:
            await check_scorer_manage_permission(
                request=mock_request,
                current_username="user@example.com",
                is_admin=False,
            )
        assert exc_info.value.status_code == 400
        assert "experiment_id" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_raises_400_when_missing_scorer_name(self) -> None:
        """Should raise 400 when scorer_name is missing."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.query_params = {"experiment_id": "exp-1"}
        mock_request.path_params = {}

        with pytest.raises(HTTPException) as exc_info:
            await check_scorer_manage_permission(
                request=mock_request,
                current_username="user@example.com",
                is_admin=False,
            )
        assert exc_info.value.status_code == 400
        assert "scorer_name" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_raises_400_when_both_missing(self) -> None:
        """Should raise 400 when both params are missing."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.query_params = {}
        mock_request.path_params = {}

        with pytest.raises(HTTPException) as exc_info:
            await check_scorer_manage_permission(
                request=mock_request,
                current_username="admin@example.com",
                is_admin=True,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_post_body_overrides_missing_query_params(self) -> None:
        """POST body should fill in missing params not in query string."""
        mock_request = MagicMock()
        mock_request.method = "PATCH"
        mock_request.query_params = {}
        mock_request.path_params = {}
        mock_request.json = AsyncMock(return_value={"experiment_id": "exp-99", "scorer_name": "recall"})

        with patch("mlflow_oidc_auth.dependencies.can_manage_scorer", return_value=True):
            result = await check_scorer_manage_permission(
                request=mock_request,
                current_username="user@example.com",
                is_admin=False,
            )
        assert result is None

    @pytest.mark.anyio
    async def test_post_body_non_dict_ignored(self) -> None:
        """POST with non-dict JSON body should not fail but fall back to query params."""
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.query_params = {"experiment_id": "exp-1", "scorer_name": "accuracy"}
        mock_request.path_params = {}
        mock_request.json = AsyncMock(return_value=["not", "a", "dict"])

        result = await check_scorer_manage_permission(
            request=mock_request,
            current_username="admin@example.com",
            is_admin=True,
        )
        assert result is None
