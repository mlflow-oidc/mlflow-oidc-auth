"""The plugin without the ``[saml]`` extra (issue #327): it imports, starts, and serves logins.

python3-saml is optional. A deployment that never installs it must be unaffected by SAML existing
at all — no import error, no route that crashes, and a ``type: saml`` provider dropped with a
reason rather than listed with a button that cannot work.

The first test runs in a subprocess with ``onelogin`` and ``xmlsec`` made unimportable, which is
the only honest way to prove the imports are lazy: in this process they are already loaded.
"""

import json
import subprocess
import sys
import textwrap

import pytest

import mlflow_oidc_auth.provider_registry as registry_module

_SCRIPT_SOURCE = """
    import json, os, sys
    sys.modules["onelogin"] = None      # ``import onelogin...`` now raises ImportError
    sys.modules["xmlsec"] = None
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    import dotenv
    dotenv.load_dotenv = lambda *a, **k: False

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.sessions import SessionMiddleware

    import mlflow_oidc_auth.provider_registry as registry
    from mlflow_oidc_auth.middleware import AuthMiddleware
    from mlflow_oidc_auth.routers import get_all_routers
    from mlflow_oidc_auth.routers.auth import auth_router
    from mlflow_oidc_auth.routers.saml import saml_router
    import mlflow_oidc_auth.routers.auth as auth_module

    class Manager:
        def __init__(self, values): self.values = values
        def get(self, key, default=None): return self.values.get(key, default)

    entries = [
        {"id": "corp", "type": "oidc", "audience": "mlflow", "issuer": "https://idp.example.test/",
         "discovery_url": "https://idp.example.test/.well-known/openid-configuration"},
        {"id": "corp-saml", "type": "saml", "entity_id": "https://sp.example.test", "idp_entity_id": "https://idp.example.test/saml",
         "idp_sso_url": "https://idp.example.test/sso", "idp_x509_cert": "not-checked-when-the-extra-is-missing"},
    ]
    result = registry.build_provider_registry(Manager({"AUTH_PROVIDERS": json.dumps(entries)}), object())
    auth_module.config.AUTH_PROVIDERS = result

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(saml_router)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-not-a-credential")
    client = TestClient(app, follow_redirects=False)

    print(json.dumps({
        "extra": registry._saml_extra_installed(),
        "providers": [p.id for p in result.providers],
        "errors": result.errors,
        "routers": len(get_all_routers()),
        "listed": [p["id"] for p in client.get("/providers").json()["providers"]],
        "providers_status": client.get("/providers").status_code,
        "acs_status": client.post("/callback/corp-saml", data={"SAMLResponse": "x"}).status_code,
        "metadata_status": client.get("/saml/metadata/corp-saml").status_code,
        "login_status": client.get("/login/corp-saml").status_code,
        "onelogin_loaded": any(name.startswith("onelogin.") for name in sys.modules),
    }))
    """
_SCRIPT = textwrap.dedent(_SCRIPT_SOURCE)


def test_the_plugin_imports_and_serves_without_the_extra(tmp_path):
    completed = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
    assert completed.returncode == 0, completed.stderr[-4000:]
    outcome = json.loads(completed.stdout.strip().splitlines()[-1])

    assert outcome["extra"] is False
    assert outcome["providers"] == ["corp"], "the SAML provider must be dropped, the OIDC one kept"
    assert any("[saml] extra" in error for error in outcome["errors"])
    assert outcome["routers"] > 0
    assert outcome["providers_status"] == 200
    assert outcome["listed"] == ["corp"]
    assert outcome["acs_status"] == 404
    assert outcome["metadata_status"] == 404
    assert outcome["login_status"] == 404
    assert outcome["onelogin_loaded"] is False


class TestInProcessDetection:
    @pytest.mark.parametrize("error", [ImportError("no module named onelogin"), OSError("libxmlsec1.so: cannot open shared object file")])
    def test_a_failed_import_reads_as_missing(self, monkeypatch, error):
        """Absent, or present with a native library that will not load — both mean no SAML."""
        import importlib

        real_import_module = importlib.import_module

        def _fail_for_saml(name, *args, **kwargs):
            if name.startswith("onelogin"):
                raise error
            return real_import_module(name, *args, **kwargs)

        monkeypatch.setattr(registry_module, "_saml_import_result", None)
        monkeypatch.setattr(importlib, "import_module", _fail_for_saml)

        assert registry_module._saml_extra_installed() is False

    @pytest.mark.skipif(not registry_module._saml_extra_installed(), reason="the [saml] extra is not installed")
    def test_it_reads_as_present_when_installed(self, monkeypatch):
        monkeypatch.setattr(registry_module, "_saml_import_result", None)

        assert registry_module._saml_extra_installed() is True
