"""Issue #366: GET gateway/secrets/config is open to non-admins, but only in redacted form.

MLflow's handler returns two server-wide flags and no per-secret data. Non-admins receive only
``secrets_available`` (which MLflow's gateway page needs to render at all); the KEK-passphrase
posture flag and any field a future MLflow release adds are withheld. Admins are unchanged.

Kept out of test_after_request.py so it can be run on its own; that file hangs when the whole
hooks/ directory is run locally.
"""

import json
from unittest.mock import patch

import pytest
from flask import Flask, jsonify
from mlflow.server import app as mlflow_app
from mlflow.server import handlers as mlflow_handlers

from mlflow_oidc_auth.hooks.after_request import (
    AFTER_REQUEST_HANDLERS,
    GATEWAY_SECRETS_CONFIG_PATH,
    _redact_gateway_secrets_config,
    after_request_hook,
)

app = Flask(__name__)

_ADMIN = "mlflow_oidc_auth.hooks.after_request.get_fastapi_admin_status"


def _run_hook(payload, *, is_admin: bool, method: str = "GET", status: int = 200):
    with app.test_request_context(path=GATEWAY_SECRETS_CONFIG_PATH, method=method):
        resp = jsonify(payload) if not isinstance(payload, (str, bytes)) else app.response_class(payload, mimetype="application/json")
        resp.status_code = status
        with patch(_ADMIN, return_value=is_admin):
            return after_request_hook(resp)


def test_handler_is_bound_to_the_route_mlflow_registers():
    assert GATEWAY_SECRETS_CONFIG_PATH == "/ajax-api/3.0/mlflow/gateway/secrets/config"
    assert GATEWAY_SECRETS_CONFIG_PATH in {str(rule) for rule in mlflow_app.url_map.iter_rules()}
    assert AFTER_REQUEST_HANDLERS[(GATEWAY_SECRETS_CONFIG_PATH, "GET")] is _redact_gateway_secrets_config


@pytest.mark.parametrize("passphrase_env", [None, "operator-set-passphrase"])
def test_real_mlflow_response_is_redacted_for_non_admin(monkeypatch, passphrase_env):
    """Drive MLflow's own handler so a change to its payload shape is caught here."""
    from mlflow.utils.crypto import CRYPTO_KEK_PASSPHRASE_ENV_VAR

    if passphrase_env is None:
        monkeypatch.delenv(CRYPTO_KEK_PASSPHRASE_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(CRYPTO_KEK_PASSPHRASE_ENV_VAR, passphrase_env)

    with mlflow_app.test_request_context(path=GATEWAY_SECRETS_CONFIG_PATH, method="GET"):
        resp = mlflow_handlers._get_secrets_config()
        assert "using_default_passphrase" in resp.get_json(), "upstream shape changed; re-review the redaction"
        with patch(_ADMIN, return_value=False):
            out = after_request_hook(resp)

    body = out.get_json()
    assert body == {"secrets_available": True}
    assert passphrase_env is None or passphrase_env not in out.get_data(as_text=True)


def test_admin_response_is_unchanged():
    payload = {"secrets_available": True, "using_default_passphrase": True}
    assert _run_hook(payload, is_admin=True).get_json() == payload


def test_non_admin_never_sees_posture_flag_or_unknown_fields():
    """Allowlist, not denylist: a value-bearing field added upstream must not leak."""
    payload = {
        "secrets_available": True,
        "using_default_passphrase": True,
        "secret_value": "sk-live-should-never-appear",
        "secrets": [{"secret_name": "other-tenant-key", "masked_value": "sk-...xyz"}],
    }
    out = _run_hook(payload, is_admin=False)
    assert out.get_json() == {"secrets_available": True}
    text = out.get_data(as_text=True)
    for leaked in ("using_default_passphrase", "sk-live", "other-tenant-key", "masked_value"):
        assert leaked not in text


def test_head_is_redacted_like_get():
    """HEAD is folded onto GET, so its Content-Length reflects the redacted body."""
    out = _run_hook({"secrets_available": True, "using_default_passphrase": False}, is_admin=False, method="HEAD")
    assert out.get_json() == {"secrets_available": True}
    assert out.content_length == len(json.dumps({"secrets_available": True}))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"using_default_passphrase": True},
        {"secrets_available": "true"},
        {"secrets_available": 1},
        {"secrets_available": False},
        ["secrets_available"],
        "not json",
    ],
)
def test_non_admin_fails_closed_on_unexpected_shape(payload):
    """Anything but a literal true reports secrets as unavailable, and no other field survives."""
    assert _run_hook(payload, is_admin=False).get_json() == {"secrets_available": False}


def test_error_responses_are_not_touched():
    out = _run_hook({"error_code": "INTERNAL_ERROR", "message": "boom"}, is_admin=False, status=500)
    assert out.get_json() == {"error_code": "INTERNAL_ERROR", "message": "boom"}


def test_response_is_independent_of_the_callers_grants():
    """The payload carries no per-secret data, so there is nothing to scope per user.

    Redaction consults no permission source (store or gateway-secret resolver), so a user
    with no grants and one with direct, group or regex secret grants get the same body.
    Per-secret visibility is enforced by ListGatewaySecretInfos / GetGatewaySecretInfo.
    """
    payload = {"secrets_available": True, "using_default_passphrase": True}
    with patch("mlflow_oidc_auth.hooks.after_request.store") as store, patch("mlflow_oidc_auth.hooks.after_request.can_read_gateway_secret") as can_read:
        no_grants = _run_hook(payload, is_admin=False).get_json()
        assert store.method_calls == []
        can_read.assert_not_called()
    assert no_grants == {"secrets_available": True}
