from unittest.mock import MagicMock, patch

from flask import Flask, request, session


def test_init_session_does_not_initialize_flask_session_in_cookie_mode():
    # Importing the module attaches routes to the underlying MLflow Flask app.
    # This test avoids reloading the module and instead unit-tests the helper.
    import mlflow_oidc_auth.app as app_module

    flask_app = MagicMock()

    with patch.object(app_module, "Session") as mock_session:
        app_module.init_session(flask_app, "cookie")
        mock_session.assert_not_called()


def test_init_session_initializes_flask_session_for_server_side_backends():
    import mlflow_oidc_auth.app as app_module

    flask_app = MagicMock()

    with patch.object(app_module, "Session") as mock_session:
        app_module.init_session(flask_app, "redis")
        mock_session.assert_called_once_with(flask_app)


def test_process_oidc_callback_succeeds_with_flask_cookie_session_across_requests():
    """
    Simulate the critical /login -> /callback flow using Flask's signed cookie session.

    This validates that session state can survive across requests solely via cookies
    (no server-side session store required), which is necessary for multi-replica
    deployments behind a load balancer without sticky sessions.
    """
    from mlflow_oidc_auth.auth import process_oidc_callback

    flask_app = Flask(__name__)
    flask_app.secret_key = "test-secret-key"

    @flask_app.get("/login")
    def _login():
        session["oauth_state"] = "state_value"
        return "ok", 200

    @flask_app.get("/callback")
    def _callback():
        email, errors = process_oidc_callback(request, session)
        if errors:
            return "\n".join(errors), 400
        session["username"] = email
        return "ok", 200

    with flask_app.test_client() as client:
        with patch("mlflow_oidc_auth.auth.get_oauth_instance") as mock_oauth, patch(
            "mlflow_oidc_auth.auth.handle_token_validation",
            return_value={"userinfo": {"email": "user@example.com"}},
        ), patch("mlflow_oidc_auth.auth.handle_user_and_group_management", return_value=[]), patch(
            "mlflow_oidc_auth.auth.app", flask_app
        ):
            mock_oauth.return_value.oidc = MagicMock()

            resp_login = client.get("/login")
            assert resp_login.status_code == 200
            # The presence of a Set-Cookie header indicates the session data is stored client-side.
            assert "Set-Cookie" in resp_login.headers

            resp_callback = client.get("/callback?state=state_value")
            assert resp_callback.status_code == 200

