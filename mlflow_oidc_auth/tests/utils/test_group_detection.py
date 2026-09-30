"""Tests for the group-detection plugin call helper (issue #250).

Plugins were originally called as ``get_user_groups(access_token)``. A plugin that declares a
``token_response`` parameter (or ``**kwargs``) is now additionally passed the token response;
everything else keeps calling the plugin exactly as before.
"""

import inspect
import sys
import types

import pytest

from mlflow_oidc_auth.utils.group_detection import _accepts_token_response, call_group_detection_plugin


def _install_module(monkeypatch, name: str, get_user_groups) -> None:
    module = types.ModuleType(name)
    module.get_user_groups = get_user_groups
    monkeypatch.setitem(sys.modules, name, module)


@pytest.fixture(autouse=True)
def _clear_signature_cache():
    """Each test gets its own plugin function object, but keep the cache tidy either way."""
    _accepts_token_response.cache_clear()
    yield
    _accepts_token_response.cache_clear()


def test_old_single_argument_signature_still_works(monkeypatch):
    calls = []

    def get_user_groups(access_token):
        calls.append(access_token)
        return ["team-a"]

    _install_module(monkeypatch, "_test_plugin_old_sig", get_user_groups)

    result = call_group_detection_plugin("_test_plugin_old_sig", "tok-123", {"access_token": "tok-123", "extra": "data"})

    assert result == ["team-a"]
    assert calls == ["tok-123"]


def test_plugin_declaring_token_response_receives_it(monkeypatch):
    received = {}

    def get_user_groups(access_token, token_response=None):
        received["access_token"] = access_token
        received["token_response"] = token_response
        return ["team-b"]

    _install_module(monkeypatch, "_test_plugin_token_response", get_user_groups)

    token_response = {"access_token": "tok-456", "id_token": "id-tok", "userinfo": {"email": "a@b.com"}}
    result = call_group_detection_plugin("_test_plugin_token_response", "tok-456", token_response)

    assert result == ["team-b"]
    assert received["access_token"] == "tok-456"
    assert received["token_response"] is token_response


def test_plugin_declaring_kwargs_receives_token_response(monkeypatch):
    received = {}

    def get_user_groups(access_token, **kwargs):
        received["access_token"] = access_token
        received.update(kwargs)
        return ["team-c"]

    _install_module(monkeypatch, "_test_plugin_kwargs", get_user_groups)

    token_response = {"access_token": "tok-789"}
    result = call_group_detection_plugin("_test_plugin_kwargs", "tok-789", token_response)

    assert result == ["team-c"]
    assert received["token_response"] is token_response


def test_plugin_declaring_keyword_only_token_response_receives_it(monkeypatch):
    received = {}

    def get_user_groups(access_token, *, token_response=None):
        received["token_response"] = token_response
        return ["team-d"]

    _install_module(monkeypatch, "_test_plugin_kwonly", get_user_groups)

    token_response = {"access_token": "tok-abc"}
    call_group_detection_plugin("_test_plugin_kwonly", "tok-abc", token_response)

    assert received["token_response"] is token_response


def test_signature_is_inspected_once_and_cached(monkeypatch):
    def get_user_groups(access_token, token_response=None):
        return []

    _install_module(monkeypatch, "_test_plugin_cache", get_user_groups)

    call_count = {"n": 0}
    real_signature = inspect.signature

    def counting_signature(func):
        call_count["n"] += 1
        return real_signature(func)

    monkeypatch.setattr(inspect, "signature", counting_signature)

    call_group_detection_plugin("_test_plugin_cache", "tok-1", {"access_token": "tok-1"})
    call_group_detection_plugin("_test_plugin_cache", "tok-2", {"access_token": "tok-2"})
    call_group_detection_plugin("_test_plugin_cache", "tok-3", {"access_token": "tok-3"})

    assert call_count["n"] == 1


@pytest.mark.parametrize("declares_token_response", [False, True])
def test_unhashable_callable_plugin_is_still_called(monkeypatch, declares_token_response):
    """A callable object defining ``__eq__`` without ``__hash__`` cannot be a cache key."""
    received = {}

    class OldDetector:
        def __eq__(self, other):
            return NotImplemented

        def __call__(self, access_token):
            received["args"] = (access_token,)
            return ["team-x"]

    class NewDetector(OldDetector):
        def __call__(self, access_token, token_response=None):
            received["args"] = (access_token, token_response)
            return ["team-x"]

    detector = NewDetector() if declares_token_response else OldDetector()
    with pytest.raises(TypeError):
        hash(detector)
    _install_module(monkeypatch, "_test_plugin_unhashable", detector)

    result = call_group_detection_plugin("_test_plugin_unhashable", "tok", {"access_token": "tok"})

    assert result == ["team-x"]
    if declares_token_response:
        assert received["args"] == ("tok", {"access_token": "tok"})
    else:
        assert received["args"] == ("tok",)
