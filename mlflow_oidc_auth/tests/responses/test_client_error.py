import pytest
from flask import Flask, jsonify
from mlflow_oidc_auth.responses.client_error import (
    make_auth_required_response,
    make_forbidden_response,
    make_basic_auth_response,
)


@pytest.fixture(scope="module")
def test_app():
    app = Flask(__name__)
    with app.app_context():
        yield app


class TestClientErrorResponses:
    def test_make_auth_required_response(self, test_app):
        response = make_auth_required_response()
        assert response.status_code == 401
        assert response.get_json() == {"message": "Authentication required"}

    def test_make_forbidden_response(self, test_app):
        response = make_forbidden_response()
        assert response.status_code == 403
        assert response.get_json() == {"message": "Permission denied"}

    def test_make_forbidden_response_custom_message(self, test_app):
        custom_msg = {"message": "Custom permission denied message"}
        response = make_forbidden_response(custom_msg)
        assert response.status_code == 403
        assert response.get_json() == custom_msg

    def test_make_basic_auth_response(self, test_app):
        response = make_basic_auth_response()
        assert response.status_code == 401
        assert response.data.decode() == ("You are not authenticated. Please see documentation for details" "https://github.com/mlflow-oidc/mlflow-oidc-auth")
        assert response.headers["WWW-Authenticate"] == 'Basic realm="mlflow"'
