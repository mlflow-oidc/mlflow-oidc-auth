import pytest
import requests
from authlib.jose.errors import BadSignatureError

from mlflow_oidc_auth import auth
from mlflow_oidc_auth.config import config


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_get_oidc_jwks_missing_discovery_url(monkeypatch):
    monkeypatch.setattr(config, "OIDC_DISCOVERY_URL", None)
    with pytest.raises(ValueError):
        auth._get_oidc_jwks()


def test_get_oidc_jwks_missing_jwks_uri(monkeypatch):
    monkeypatch.setattr(config, "OIDC_DISCOVERY_URL", "http://example/.well-known")

    def fake_get(url):
        return DummyResponse({})

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(ValueError):
        auth._get_oidc_jwks()


def test_get_oidc_jwks_success(monkeypatch):
    monkeypatch.setattr(config, "OIDC_DISCOVERY_URL", "http://example/.well-known")

    calls = []

    def fake_get(url):
        calls.append(url)
        if url == "http://example/.well-known":
            return DummyResponse({"jwks_uri": "http://jwks"})
        if url == "http://jwks":
            return DummyResponse({"keys": []})
        raise RuntimeError("unexpected url")

    monkeypatch.setattr(requests, "get", fake_get)

    jwks = auth._get_oidc_jwks()
    assert jwks == {"keys": []}
    assert calls == ["http://example/.well-known", "http://jwks"]


def test_get_oidc_jwks_request_exception(monkeypatch):
    monkeypatch.setattr(config, "OIDC_DISCOVERY_URL", "http://example/.well-known")

    def fake_get(url):
        raise requests.exceptions.RequestException("boom")

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(requests.exceptions.RequestException):
        auth._get_oidc_jwks()


class Payload:
    def __init__(self):
        self.validated = False

    def validate(self):
        self.validated = True


def test_validate_token_success(monkeypatch):
    monkeypatch.setattr(auth, "_get_oidc_jwks", lambda: {"keys": []})

    payload = Payload()

    def fake_decode(token, jwks):
        assert jwks == {"keys": []}
        return payload

    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    result = auth.validate_token("tok")
    assert result is payload
    assert payload.validated


def test_validate_token_bad_signature_retries(monkeypatch):
    monkeypatch.setattr(auth, "_get_oidc_jwks", lambda: {"keys": []})

    payload = Payload()
    calls = {"count": 0}

    def fake_decode(token, jwks):
        calls["count"] += 1
        if calls["count"] == 1:
            raise BadSignatureError("bad sig")
        return payload

    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    result = auth.validate_token("tok")
    assert result is payload
    assert payload.validated
    assert calls["count"] == 2


def test_validate_token_other_exception_propagates(monkeypatch):
    monkeypatch.setattr(auth, "_get_oidc_jwks", lambda: {"keys": []})

    def fake_decode(token, jwks):
        raise ValueError("boom")

    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    with pytest.raises(ValueError):
        auth.validate_token("tok")
