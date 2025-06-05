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
    with app.test_request_context(path="/protected", method="GET", headers={"Authorization": "Basic invalid"}):
        with patch("mlflow_oidc_auth.hooks.before_request.authenticate_request_basic_auth", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request.render_template", return_value=Response("Unauthorized", status=401)
        ):
            response = before_request_hook()
            assert response.status_code == 401  # type: ignore
            assert b"Unauthorized" in response.data  # type: ignore


def test_bearer_auth_failure(client):
    with app.test_request_context(path="/protected", method="GET", headers={"Authorization": "Bearer invalid"}):
        with patch("mlflow_oidc_auth.hooks.before_request.authenticate_request_bearer_token", return_value=False):
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


def test_authorization_failure(client):
    with app.test_request_context(path="/protected", method="GET"):
        with patch("mlflow_oidc_auth.hooks.before_request.get_is_admin", return_value=False), patch(
            "mlflow_oidc_auth.hooks.before_request.BEFORE_REQUEST_VALIDATORS", {("/protected", "GET"): lambda: False}
        ), patch("mlflow_oidc_auth.hooks.before_request.render_template", return_value=Response("Forbidden", status=403)):
            response = before_request_hook()
            assert response.status_code == 403  # type: ignore
            assert b"Forbidden" in response.data  # type: ignore
