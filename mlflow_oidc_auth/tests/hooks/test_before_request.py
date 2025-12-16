import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, session, request, Response
from mlflow_oidc_auth.hooks.before_request import before_request_hook
from mlflow_oidc_auth import responses
from mlflow_oidc_auth.config import config

app = Flask(__name__)
app.secret_key = "test_secret_key"


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


def test_unprotected_route(client):
    with app.test_request_context(path="/health", method="GET"):
        assert before_request_hook() is None  # No response for unprotected routes


def test_basic_auth_failure(client):
    with app.test_request_context(path="/protected", method="GET"):
        # Mock the request.authorization object
        mock_auth = MagicMock()
        mock_auth.type = "basic"

        with patch("mlflow_oidc_auth.hooks.before_request.request") as mock_request, patch(
            "mlflow_oidc_auth.hooks.before_request.authenticate_request_basic_auth", return_value=False
        ), patch("mlflow_oidc_auth.hooks.before_request.responses.make_basic_auth_response", return_value=Response("Unauthorized", status=401)):
            mock_request.path = "/protected"
            mock_request.method = "GET"
            mock_request.authorization = mock_auth

            response = before_request_hook()
            assert response.status_code == 401  # type: ignore
            assert b"Unauthorized" in response.data  # type: ignore


def test_bearer_auth_failure(client):
    with app.test_request_context(path="/protected", method="GET"):
        # Mock the request.authorization object
        mock_auth = MagicMock()
        mock_auth.type = "bearer"

        with patch("mlflow_oidc_auth.hooks.before_request.request") as mock_request, patch(
            "mlflow_oidc_auth.hooks.before_request.authenticate_request_bearer_token", return_value=False
        ), patch("mlflow_oidc_auth.hooks.before_request.responses.make_auth_required_response", return_value=Response("Unauthorized", status=401)):
            mock_request.path = "/protected"
            mock_request.method = "GET"
            mock_request.authorization = mock_auth

            response = before_request_hook()
            assert response.status_code == 401  # type: ignore


def test_session_redirect(client):
    with app.test_request_context(path="/protected", method="GET"):
        session.clear()
        with patch("mlflow_oidc_auth.hooks.before_request.config.AUTOMATIC_LOGIN_REDIRECT", True), patch(
            "mlflow_oidc_auth.hooks.before_request.url_for", return_value="/login"
        ):
            response = before_request_hook()
            assert response.status_code == 302  # type: ignore
            assert response.location.endswith("/login")  # type: ignore


def test_otlp_ingest_no_auth_returns_401(client):
    """OTLP ingest endpoints must not redirect or render HTML when auth is missing."""
    with app.test_request_context(path="/v1/traces", method="POST"):
        session.clear()
        with patch("mlflow_oidc_auth.hooks.before_request.config.AUTOMATIC_LOGIN_REDIRECT", True):
            response = before_request_hook()
            assert response is not None
            assert response.status_code == 401  # type: ignore


def test_authorization_failure(client):
    with app.test_request_context(path="/protected", method="GET"):
        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS", {("/protected", "GET"): lambda: False}
        ), patch("mlflow_oidc_auth.hooks.before_request.render_template", return_value=Response("Forbidden", status=403)):
            response = before_request_hook()
            assert response.status_code == 403  # type: ignore
            assert b"Forbidden" in response.data  # type: ignore


def test_basic_auth_success(client):
    """Test successful basic authentication"""
    with app.test_request_context(path="/protected", method="GET"):
        # Mock the request.authorization object
        mock_auth = MagicMock()
        mock_auth.type = "basic"

        with patch("mlflow_oidc_auth.hooks.before_request.request") as mock_request, patch(
            "mlflow_oidc_auth.hooks.before_request.authenticate_request_basic_auth", return_value=True
        ), patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS", {("/protected", "GET"): lambda: True}
        ):
            mock_request.path = "/protected"
            mock_request.method = "GET"
            mock_request.authorization = mock_auth

            response = before_request_hook()
            assert response is None  # No response means authentication succeeded


def test_bearer_auth_success(client):
    """Test successful bearer token authentication"""
    with app.test_request_context(path="/protected", method="GET", headers={"Authorization": "Bearer valid"}):
        with patch("mlflow_oidc_auth.hooks.before_request.authenticate_request_bearer_token", return_value=True), patch(
            "mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False
        ), patch("mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS", {("/protected", "GET"): lambda: True}):
            response = before_request_hook()
            assert response is None  # No response means authentication succeeded


def test_session_no_redirect(client):
    """Test session authentication without automatic redirect"""
    with app.test_request_context(path="/protected", method="GET"):
        session.clear()
        with patch("mlflow_oidc_auth.hooks.before_request.config.AUTOMATIC_LOGIN_REDIRECT", False), patch(
            "mlflow_oidc_auth.hooks.before_request.render_template", return_value=Response("Auth required", status=200)
        ) as mock_render:
            response = before_request_hook()
            assert response.status_code == 200  # type: ignore
            mock_render.assert_called_once_with(
                "auth.html",
                username=None,
                provide_display_name=config.OIDC_PROVIDER_DISPLAY_NAME,
            )


def test_admin_bypass(client):
    """Test that admin users bypass authorization"""
    with app.test_request_context(path="/protected", method="GET"):
        session["username"] = "admin"
        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=True):
            response = before_request_hook()
            assert response is None  # Admin should bypass authorization


def test_authorization_success(client):
    """Test successful authorization"""
    with app.test_request_context(path="/protected", method="GET"):
        session["username"] = "user"
        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS", {("/protected", "GET"): lambda: True}
        ):
            response = before_request_hook()
            assert response is None  # Authorization succeeded


def test_find_validator_logged_models(client):
    """Test _find_validator for logged model routes"""
    from mlflow_oidc_auth.hooks.before_request import _find_validator

    mock_request = MagicMock()
    mock_request.path = "/api/2.0/mlflow/logged-models/12345"
    mock_request.method = "GET"

    mock_pattern = MagicMock()
    mock_pattern.fullmatch.return_value = True
    mock_validator = lambda: True

    with patch("mlflow_oidc_auth.hooks.before_request.LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS", {(mock_pattern, "GET"): mock_validator}):
        result = _find_validator(mock_request)
        assert result == mock_validator


def test_find_validator_regular_routes(client):
    """Test _find_validator for regular routes"""
    from mlflow_oidc_auth.hooks.before_request import _find_validator

    mock_request = MagicMock()
    mock_request.path = "/api/2.0/mlflow/experiments/create"
    mock_request.method = "POST"

    mock_validator = lambda: True

    with patch("mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS", {("/api/2.0/mlflow/experiments/create", "POST"): mock_validator}):
        result = _find_validator(mock_request)
        assert result == mock_validator


def test_find_validator_no_match(client):
    """Test _find_validator when no validator is found"""
    from mlflow_oidc_auth.hooks.before_request import _find_validator

    mock_request = MagicMock()
    mock_request.path = "/unknown/path"
    mock_request.method = "GET"

    with patch("mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS", {}), patch(
        "mlflow_oidc_auth.hooks.before_request.LOGGED_MODEL_BEFORE_REQUEST_VALIDATORS", {}
    ):
        result = _find_validator(mock_request)
        assert result is None


def test_is_proxy_artifact_path(client):
    """Test _is_proxy_artifact_path function"""
    from mlflow_oidc_auth.hooks.before_request import _is_proxy_artifact_path

    # Test positive case
    assert _is_proxy_artifact_path("/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt") is True

    # Test negative case
    assert _is_proxy_artifact_path("/api/2.0/mlflow/experiments/search") is False


def test_get_proxy_artifact_validator_no_view_args(client):
    """Test _get_proxy_artifact_validator with no view_args (list operation)"""
    from mlflow_oidc_auth.hooks.before_request import _get_proxy_artifact_validator
    from mlflow_oidc_auth.validators import validate_can_read_experiment_artifact_proxy

    result = _get_proxy_artifact_validator("GET", None)
    assert result == validate_can_read_experiment_artifact_proxy


def test_get_proxy_artifact_validator_with_view_args(client):
    """Test _get_proxy_artifact_validator with view_args for different methods"""
    from mlflow_oidc_auth.hooks.before_request import _get_proxy_artifact_validator
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


def test_proxy_artifact_authorization_success(client):
    """Test proxy artifact path authorization success"""
    with app.test_request_context(path="/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt", method="GET"):
        session["username"] = "user"
        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None
        ), patch("mlflow_oidc_auth.hooks.before_request.validate_can_read_experiment_artifact_proxy", return_value=True):
            response = before_request_hook()
            assert response is None  # Authorization succeeded


def test_proxy_artifact_authorization_failure(client):
    """Test proxy artifact path authorization failure"""
    with app.test_request_context(path="/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt", method="GET"):
        session["username"] = "user"
        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None
        ), patch("mlflow_oidc_auth.hooks.before_request.validate_can_read_experiment_artifact_proxy", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request.responses.make_forbidden_response", return_value=Response("Forbidden", status=403)
        ) as mock_forbidden:
            response = before_request_hook()
            assert response.status_code == 403  # type: ignore
            mock_forbidden.assert_called_once()


def test_proxy_artifact_no_validator(client):
    """Test proxy artifact path when no validator is found"""
    with app.test_request_context(path="/api/2.0/mlflow-artifacts/artifacts/experiment1/file.txt", method="PATCH"):  # Unsupported method
        session["username"] = "user"
        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None
        ):
            response = before_request_hook()
            assert response is None  # No validator, so no authorization check


def test_logged_model_route_authorization(client):
    """Test authorization for logged model routes"""
    with app.test_request_context(path="/api/2.0/mlflow/logged-models/12345", method="GET"):
        session["username"] = "user"
        mock_validator = MagicMock(return_value=True)

        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request._find_validator", return_value=mock_validator
        ):
            response = before_request_hook()
            assert response is None  # Authorization succeeded
            mock_validator.assert_called_once()


def test_logged_model_route_authorization_failure(client):
    """Test authorization failure for logged model routes"""
    with app.test_request_context(path="/api/2.0/mlflow/logged-models/12345", method="GET"):
        session["username"] = "user"
        mock_validator = MagicMock(return_value=False)

        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request._find_validator", return_value=mock_validator
        ), patch("mlflow_oidc_auth.hooks.before_request.responses.make_forbidden_response", return_value=Response("Forbidden", status=403)) as mock_forbidden:
            response = before_request_hook()
            assert response.status_code == 403  # type: ignore
            mock_validator.assert_called_once()
            mock_forbidden.assert_called_once()


def test_no_validator_found(client):
    """Test when no validator is found for a route"""
    with app.test_request_context(path="/unknown/route", method="GET"):
        session["username"] = "user"

        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request._find_validator", return_value=None
        ), patch("mlflow_oidc_auth.hooks.before_request._is_proxy_artifact_path", return_value=False):
            response = before_request_hook()
            assert response is None  # No validator, so no authorization check
