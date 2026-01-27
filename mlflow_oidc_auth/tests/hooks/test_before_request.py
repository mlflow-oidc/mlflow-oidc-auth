import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, Response
from mlflow_oidc_auth.hooks.before_request import (
    before_request_hook,
    _find_validator,
    _is_proxy_artifact_path,
    _get_proxy_artifact_validator,
    _re_compile_path,
    BEFORE_REQUEST_VALIDATORS,
    LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS,
)

app = Flask(__name__)
app.secret_key = "test_secret_key"


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_bridge():
    with (
        patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_username", return_value="test_user") as mock_username,
        patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False) as mock_is_admin,
    ):
        yield mock_username, mock_is_admin


def test_before_request_hook_admin_bypass(client, mock_bridge):
    """Test that admin users bypass authorization"""
    with app.test_request_context(path="/protected", method="GET"):
        with patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=True):
            response = before_request_hook()
            assert response is None  # Admin should bypass authorization


def test_before_request_hook_no_validator(client, mock_bridge):
    """Test when no validator is found for a route"""
    with app.test_request_context(path="/unknown/route", method="GET"):
        with (
            patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None),
            patch("mlflow_oidc_auth.hooks.before_request._is_proxy_artifact_path", return_value=False),
        ):
            response = before_request_hook()
            assert response is None  # No validator, so no authorization check


def test_before_request_hook_validator_success(client, mock_bridge):
    """Test successful authorization with validator"""
    mock_validator = MagicMock(return_value=True)

    with app.test_request_context(path="/protected", method="GET"):
        with (
            patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=mock_validator),
            patch("mlflow_oidc_auth.hooks.before_request._is_proxy_artifact_path", return_value=False),
        ):
            response = before_request_hook()
            assert response is None  # Authorization succeeded
            mock_validator.assert_called_once_with("test_user")


def test_before_request_hook_validator_failure(client, mock_bridge):
    """Test authorization failure with validator"""
    mock_validator = MagicMock(return_value=False)

    with app.test_request_context(path="/protected", method="GET"):
        with (
            patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=mock_validator),
            patch("mlflow_oidc_auth.hooks.before_request._is_proxy_artifact_path", return_value=False),
            patch("mlflow_oidc_auth.hooks.before_request.responses.make_forbidden_response", return_value=Response("Forbidden", status=403)) as mock_forbidden,
        ):
            response = before_request_hook()
            assert response.status_code == 403  # type: ignore
            mock_validator.assert_called_once_with("test_user")
            mock_forbidden.assert_called_once()


def test_find_validator_logged_models():
    """Test _find_validator for logged model routes"""
    mock_request = MagicMock()
    mock_request.path = "/api/2.0/mlflow/logged-models/12345"
    mock_request.method = "GET"

    mock_pattern = MagicMock()
    mock_pattern.fullmatch.return_value = True
    mock_validator = lambda: True

    with patch("mlflow_oidc_auth.hooks.before_request.LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS", {(mock_pattern, "GET"): mock_validator}):
        result = _find_validator(mock_request)
        assert result == mock_validator
        mock_pattern.fullmatch.assert_called_once_with("/api/2.0/mlflow/logged-models/12345")


def test_find_validator_logged_models_no_match():
    """Test _find_validator for logged model routes with no match"""
    mock_request = MagicMock()
    mock_request.path = "/api/2.0/mlflow/logged-models/12345"
    mock_request.method = "GET"

    mock_pattern = MagicMock()
    mock_pattern.fullmatch.return_value = False
    mock_validator = lambda: True

    with patch("mlflow_oidc_auth.hooks.before_request.LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS", {(mock_pattern, "GET"): mock_validator}):
        result = _find_validator(mock_request)
        assert result is None
        mock_pattern.fullmatch.assert_called_once_with("/api/2.0/mlflow/logged-models/12345")


def test_find_validator_regular_routes():
    """Test _find_validator for regular routes"""
    mock_request = MagicMock()
    mock_request.path = "/api/2.0/mlflow/experiments/create"
    mock_request.method = "POST"

    mock_validator = lambda: True

    with patch("mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS", {("/api/2.0/mlflow/experiments/create", "POST"): mock_validator}):
        result = _find_validator(mock_request)
        assert result == mock_validator


def test_find_validator_no_match():
    """Test _find_validator when no validator is found"""
    mock_request = MagicMock()
    mock_request.path = "/unknown/path"
    mock_request.method = "GET"

    with (
        patch("mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS", {}),
        patch("mlflow_oidc_auth.hooks.before_request.LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS", {}),
    ):
        result = _find_validator(mock_request)
        assert result is None


def test_re_compile_path():
    """Test _re_compile_path function"""
    # Test path with angle brackets
    pattern = _re_compile_path("/api/2.0/experiments/<experiment_id>")
    assert pattern.pattern == "/api/2.0/experiments/([^/]+)"

    # Test path without angle brackets
    pattern = _re_compile_path("/api/2.0/experiments/search")
    assert pattern.pattern == "/api/2.0/experiments/search"

    # Test path with multiple parameters
    pattern = _re_compile_path("/api/2.0/experiments/<experiment_id>/runs/<run_id>")
    assert pattern.pattern == "/api/2.0/experiments/([^/]+)/runs/([^/]+)"


def test_re_compile_path_matching():
    """Test that _re_compile_path creates working regex patterns"""
    pattern = _re_compile_path("/api/2.0/experiments/<experiment_id>")

    # Should match valid paths
    assert pattern.fullmatch("/api/2.0/experiments/123") is not None
    assert pattern.fullmatch("/api/2.0/experiments/abc-def") is not None

    # Should not match invalid paths
    assert pattern.fullmatch("/api/2.0/experiments/") is None
    assert pattern.fullmatch("/api/2.0/experiments/123/extra") is None
    assert pattern.fullmatch("/api/2.0/other/123") is None


def test_is_proxy_artifact_path():
    """Test _is_proxy_artifact_path function"""
    # Test positive case
    assert _is_proxy_artifact_path("/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt") is True

    # Test negative case
    assert _is_proxy_artifact_path("/api/2.0/mlflow/experiments/search") is False

    # Test edge cases
    assert _is_proxy_artifact_path("/api/2.0/mlflow-artifacts/artifacts/") is True
    assert _is_proxy_artifact_path("/api/2.0/mlflow-artifacts/other") is False


def test_get_proxy_artifact_validator_no_view_args():
    """Test _get_proxy_artifact_validator with no view_args (list operation)"""
    from mlflow_oidc_auth.validators import validate_can_read_experiment_artifact_proxy

    result = _get_proxy_artifact_validator("GET", None)
    assert result == validate_can_read_experiment_artifact_proxy


def test_get_proxy_artifact_validator_with_view_args():
    """Test _get_proxy_artifact_validator with view_args for different methods"""
    from mlflow_oidc_auth.validators import (
        validate_can_read_experiment_artifact_proxy,
        validate_can_update_experiment_artifact_proxy,
        validate_can_delete_experiment_artifact_proxy,
    )

    view_args = {"experiment_id": "123"}

    # Test GET (download)
    result = _get_proxy_artifact_validator("GET", view_args)
    assert result == validate_can_read_experiment_artifact_proxy

    # Test PUT (upload)
    result = _get_proxy_artifact_validator("PUT", view_args)
    assert result == validate_can_update_experiment_artifact_proxy

    # Test DELETE
    result = _get_proxy_artifact_validator("DELETE", view_args)
    assert result == validate_can_delete_experiment_artifact_proxy

    # Test unsupported method
    result = _get_proxy_artifact_validator("PATCH", view_args)
    assert result is None


def test_proxy_artifact_authorization_success(client, mock_bridge):
    """Test proxy artifact path authorization success"""
    with app.test_request_context(path="/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt", method="GET"):
        with (
            patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None),
            patch("mlflow_oidc_auth.hooks.before_request.validate_can_read_experiment_artifact_proxy", return_value=True) as mock_validator,
        ):
            response = before_request_hook()
            assert response is None  # Authorization succeeded
            mock_validator.assert_called_once_with("test_user")


def test_proxy_artifact_authorization_failure(client, mock_bridge):
    """Test proxy artifact path authorization failure"""
    with app.test_request_context(path="/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt", method="GET"):
        with (
            patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None),
            patch("mlflow_oidc_auth.hooks.before_request.validate_can_read_experiment_artifact_proxy", return_value=False) as mock_validator,
            patch("mlflow_oidc_auth.hooks.before_request.responses.make_forbidden_response", return_value=Response("Forbidden", status=403)) as mock_forbidden,
        ):
            response = before_request_hook()
            assert response.status_code == 403  # type: ignore
            mock_validator.assert_called_once_with("test_user")
            mock_forbidden.assert_called_once()


def test_proxy_artifact_no_validator(client, mock_bridge):
    """Test proxy artifact path when no validator is found"""
    with app.test_request_context(path="/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt", method="PATCH"):  # Unsupported method
        with patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None):
            response = before_request_hook()
            assert response is None  # No validator, so no authorization check


def test_proxy_artifact_upload_authorization(client, mock_bridge):
    """Test proxy artifact path authorization for upload (PUT)"""
    with app.test_request_context(path="/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt", method="PUT"):
        # Mock request.view_args to simulate Flask route matching
        with patch("mlflow_oidc_auth.hooks.before_request.request") as mock_request:
            mock_request.path = "/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt"
            mock_request.method = "PUT"
            mock_request.view_args = {"experiment_id": "experiment1"}

            with (
                patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None),
                patch("mlflow_oidc_auth.hooks.before_request.validate_can_update_experiment_artifact_proxy", return_value=True) as mock_validator,
            ):
                response = before_request_hook()
                assert response is None  # Authorization succeeded
                mock_validator.assert_called_once_with("test_user")


def test_proxy_artifact_delete_authorization(client, mock_bridge):
    """Test proxy artifact path authorization for delete"""
    with app.test_request_context(path="/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt", method="DELETE"):
        # Mock request.view_args to simulate Flask route matching
        with patch("mlflow_oidc_auth.hooks.before_request.request") as mock_request:
            mock_request.path = "/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt"
            mock_request.method = "DELETE"
            mock_request.view_args = {"experiment_id": "experiment1"}

            with (
                patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None),
                patch("mlflow_oidc_auth.hooks.before_request.validate_can_delete_experiment_artifact_proxy", return_value=True) as mock_validator,
            ):
                response = before_request_hook()
                assert response is None  # Authorization succeeded
                mock_validator.assert_called_once_with("test_user")


def test_logged_model_route_authorization(client, mock_bridge):
    """Test authorization for logged model routes"""
    with app.test_request_context(path="/api/2.0/mlflow/logged-models/12345", method="GET"):
        mock_validator = MagicMock(return_value=True)

        with patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=mock_validator):
            response = before_request_hook()
            assert response is None  # Authorization succeeded
            mock_validator.assert_called_once_with("test_user")


def test_logged_model_route_authorization_failure(client, mock_bridge):
    """Test authorization failure for logged model routes"""
    with app.test_request_context(path="/api/2.0/mlflow/logged-models/12345", method="GET"):
        mock_validator = MagicMock(return_value=False)

        with (
            patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=mock_validator),
            patch("mlflow_oidc_auth.hooks.before_request.responses.make_forbidden_response", return_value=Response("Forbidden", status=403)) as mock_forbidden,
        ):
            response = before_request_hook()
            assert response.status_code == 403  # type: ignore
            mock_validator.assert_called_once_with("test_user")
            mock_forbidden.assert_called_once()


def test_before_request_hook_debug_logging(client, mock_bridge):
    """Test that debug logging is called with correct parameters"""
    with app.test_request_context(path="/test/path", method="POST"):
        with (
            patch("mlflow_oidc_auth.hooks.before_request.logger.debug") as mock_debug,
            patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None),
            patch("mlflow_oidc_auth.hooks.before_request._is_proxy_artifact_path", return_value=False),
        ):
            before_request_hook()
            mock_debug.assert_called_once_with("Before request hook called for path: /test/path, method: POST, username: test_user, is admin: False")


def test_before_request_hook_execution_order(client, mock_bridge):
    """Test that hook execution follows the correct order: admin check -> validator -> proxy artifact"""
    with app.test_request_context(path="/test/path", method="GET"):
        mock_validator = MagicMock(return_value=True)

        with (
            patch("mlflow_oidc_auth.hooks.before_request.get_fastapi_admin_status", return_value=False) as mock_admin,
            patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=mock_validator) as mock_find_validator,
            patch("mlflow_oidc_auth.hooks.before_request._is_proxy_artifact_path", return_value=False) as mock_is_proxy,
        ):
            before_request_hook()

            # Verify execution order by checking call order
            mock_admin.assert_called_once()
            mock_find_validator.assert_called_once()
            # _is_proxy_artifact_path should not be called since validator was found
            mock_is_proxy.assert_not_called()
            mock_validator.assert_called_once_with("test_user")


def test_before_request_hook_dependency_management(client, mock_bridge):
    """Test that hook properly manages dependencies between validators and proxy artifacts"""
    with app.test_request_context(path="/api/2.0/mlflow-artifacts/artifacts/exp1/file.txt", method="GET"):
        # When no regular validator is found, should check proxy artifacts
        with (
            patch("mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None) as mock_find_validator,
            patch("mlflow_oidc_auth.hooks.before_request._is_proxy_artifact_path", return_value=True) as mock_is_proxy,
            patch("mlflow_oidc_auth.hooks.before_request._get_proxy_artifact_validator", return_value=None) as mock_get_proxy_validator,
        ):
            response = before_request_hook()
            assert response is None  # No validator found, so no authorization check

            # Verify dependency chain
            mock_find_validator.assert_called_once()
            mock_is_proxy.assert_called_once_with("/api/2.0/mlflow-artifacts/artifacts/exp1/file.txt")
            mock_get_proxy_validator.assert_called_once_with("GET", None)


def test_logged_model_before_request_validators_structure():
    """Test that LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS has correct structure"""
    # Verify that the validators dictionary contains compiled regex patterns
    assert len(LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS) > 0

    for (pattern, method), validator in LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS.items():
        # Pattern should be a compiled regex
        assert hasattr(pattern, "fullmatch"), f"Pattern {pattern} should be a compiled regex"
        # Method should be a string
        assert isinstance(method, str), f"Method {method} should be a string"
        # Validator should be callable or None (some endpoints may not have validators)
        assert validator is None or callable(validator), f"Validator {validator} should be callable or None"


def test_before_request_validators_structure():
    """Test that BEFORE_REQUEST_VALIDATORS has correct structure"""
    # Verify that the validators dictionary has the expected structure
    assert len(BEFORE_REQUEST_VALIDATORS) > 0

    for (path, method), validator in BEFORE_REQUEST_VALIDATORS.items():
        # Path should be a string
        assert isinstance(path, str), f"Path {path} should be a string"
        # Method should be a string
        assert isinstance(method, str), f"Method {method} should be a string"
        # Validator should be callable or None (some endpoints may not have validators)
        assert validator is None or callable(validator), f"Validator {validator} should be callable or None"
