"""The session token vault (issue #367): what reaches ``auth_sessions.encrypted_tokens``."""

import base64
import logging

import pytest
from cryptography.fernet import Fernet

from mlflow_oidc_auth.session.token_vault import SessionTokens, TokenVault, get_token_vault

# Test-only values, never credentials: they exist only inside this process.
SECRET = "test-secret-key-not-a-credential"
OTHER_SECRET = "a-different-test-secret-not-a-credential"
REFRESH = "rt-sensitive-value-0123456789"
ID_TOKEN = "idt-sensitive-value-9876543210"


def _tokens(**overrides) -> SessionTokens:
    values = dict(provider_id="default", expires_at=1_900_000_000, refresh_token=REFRESH, id_token=ID_TOKEN)
    values.update(overrides)
    return SessionTokens(**values)


class TestRoundTrip:
    def test_derived_key_round_trip(self):
        vault = TokenVault(SECRET)
        tokens = _tokens(saml_name_id="nid", saml_name_id_format="fmt", saml_session_index="idx")

        assert vault.decrypt(vault.encrypt(tokens)) == tokens

    def test_dedicated_key_round_trip(self):
        vault = TokenVault(SECRET, Fernet.generate_key().decode())
        assert vault.decrypt(vault.encrypt(_tokens())) == _tokens()

    def test_ciphertext_contains_no_token_material(self):
        blob = TokenVault(SECRET).encrypt(_tokens())

        assert REFRESH not in blob and ID_TOKEN not in blob
        assert REFRESH.encode() not in base64.urlsafe_b64decode(blob.encode())

    def test_encryption_is_randomised(self):
        vault = TokenVault(SECRET)
        assert vault.encrypt(_tokens()) != vault.encrypt(_tokens())

    def test_dedicated_key_is_not_the_derived_one(self):
        """With a dedicated key configured, SECRET_KEY alone cannot read the blobs."""
        blob = TokenVault(SECRET, Fernet.generate_key().decode()).encrypt(_tokens())
        assert TokenVault(SECRET).decrypt(blob) is None

    def test_rotated_dedicated_key_still_decrypts_old_blobs(self):
        old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
        blob = TokenVault(SECRET, old).encrypt(_tokens())

        assert TokenVault(SECRET, f"{new},{old}").decrypt(blob) == _tokens()


class TestRefusal:
    def test_wrong_secret_returns_none(self):
        blob = TokenVault(SECRET).encrypt(_tokens())
        assert TokenVault(OTHER_SECRET).decrypt(blob) is None

    def test_wrong_dedicated_key_returns_none(self):
        blob = TokenVault(SECRET, Fernet.generate_key().decode()).encrypt(_tokens())
        assert TokenVault(SECRET, Fernet.generate_key().decode()).decrypt(blob) is None

    @pytest.mark.parametrize("position", [10, 40, -5])
    def test_tampered_blob_returns_none(self, position):
        vault = TokenVault(SECRET)
        blob = vault.encrypt(_tokens())
        chars = list(blob)
        chars[position] = "A" if chars[position] != "A" else "B"

        assert vault.decrypt("".join(chars)) is None

    @pytest.mark.parametrize("blob", [None, "", "not-a-token", "gAAAAA", 42])
    def test_garbage_returns_none(self, blob):
        assert TokenVault(SECRET).decrypt(blob) is None

    def test_non_object_payload_returns_none(self):
        vault = TokenVault(SECRET)
        blob = vault._fernet.encrypt(b"[1, 2, 3]").decode()
        assert vault.decrypt(blob) is None

    @pytest.mark.parametrize("bad", ["short", "not base64 !!", base64.urlsafe_b64encode(b"x" * 31).decode()])
    def test_malformed_dedicated_key_is_refused(self, bad):
        with pytest.raises(ValueError) as excinfo:
            TokenVault(SECRET, bad)
        assert bad not in str(excinfo.value), "the key value must not be echoed"

    def test_no_key_at_all_is_refused(self):
        with pytest.raises(ValueError):
            TokenVault(None)


class TestForwardCompatibility:
    def test_unknown_keys_are_ignored(self):
        data = _tokens().to_dict()
        data["added_in_a_future_release"] = "value"

        assert SessionTokens.from_dict(data) == _tokens()

    def test_unknown_keys_survive_encryption_path(self):
        vault = TokenVault(SECRET)
        data = _tokens().to_dict() | {"future": 1}
        blob = vault._fernet.encrypt(__import__("json").dumps(data).encode()).decode()

        assert vault.decrypt(blob) == _tokens()

    def test_non_numeric_expiry_is_dropped(self):
        assert SessionTokens.from_dict({"expires_at": "soon"}).expires_at is None
        assert SessionTokens.from_dict({"expires_at": 12.7}).expires_at == 12


class TestSessionTokens:
    def test_has_refresh_token(self):
        assert _tokens().has_refresh_token is True
        assert _tokens(refresh_token=None).has_refresh_token is False
        assert _tokens(refresh_token="").has_refresh_token is False

    def test_is_expired(self):
        assert SessionTokens(expires_at=100).is_expired(now=100) is True
        assert SessionTokens(expires_at=100).is_expired(now=99) is False
        assert SessionTokens(expires_at=100).is_expired(leeway_seconds=10, now=90) is True
        assert SessionTokens(expires_at=None).is_expired(now=10**12) is False

    def test_repr_hides_token_material(self):
        text = repr(_tokens())
        assert REFRESH not in text and ID_TOKEN not in text
        assert "has_refresh_token=True" in text


class TestNoTokenMaterialInLogs:
    def test_failed_decrypt_logs_nothing_sensitive(self, caplog):
        vault = TokenVault(SECRET)
        blob = vault.encrypt(_tokens())
        with caplog.at_level(logging.DEBUG):
            assert TokenVault(OTHER_SECRET).decrypt(blob) is None
            assert vault.decrypt(blob[:-4] + "AAAA") is None

        logged = "\n".join(record.getMessage() for record in caplog.records) + caplog.text
        assert blob not in logged
        assert blob[:-4] not in logged
        assert REFRESH not in logged and ID_TOKEN not in logged
        assert SECRET not in logged

    def test_round_trip_logs_nothing(self, caplog):
        vault = TokenVault(SECRET)
        with caplog.at_level(logging.DEBUG):
            vault.decrypt(vault.encrypt(_tokens()))

        assert REFRESH not in caplog.text and ID_TOKEN not in caplog.text


class TestGetTokenVault:
    def test_uses_dedicated_key_when_configured(self, monkeypatch):
        from mlflow_oidc_auth.config import config

        key = Fernet.generate_key().decode()
        monkeypatch.setattr(config, "SESSION_TOKEN_ENCRYPTION_KEY", key, raising=False)
        blob = get_token_vault().encrypt(_tokens())

        assert TokenVault(None, key).decrypt(blob) == _tokens()

    def test_derives_from_secret_key_otherwise(self, monkeypatch):
        from mlflow_oidc_auth.config import config

        monkeypatch.setattr(config, "SESSION_TOKEN_ENCRYPTION_KEY", None, raising=False)
        monkeypatch.setattr(config, "SECRET_KEY", SECRET)

        assert TokenVault(SECRET).decrypt(get_token_vault().encrypt(_tokens())) == _tokens()

    def test_is_cached_per_key(self, monkeypatch):
        from mlflow_oidc_auth.config import config

        monkeypatch.setattr(config, "SESSION_TOKEN_ENCRYPTION_KEY", None, raising=False)
        monkeypatch.setattr(config, "SECRET_KEY", SECRET)
        first = get_token_vault()
        assert get_token_vault() is first

        monkeypatch.setattr(config, "SECRET_KEY", OTHER_SECRET)
        assert get_token_vault() is not first


class TestStartupValidation:
    """A malformed ``SESSION_TOKEN_ENCRYPTION_KEY`` fails when config loads, not at first login."""

    @pytest.mark.parametrize("value", [None, "", Fernet.generate_key().decode()])
    def test_unset_or_valid_passes(self, value):
        from mlflow_oidc_auth.session.token_vault import validate_encryption_key

        validate_encryption_key(value)

    def test_malformed_is_refused_without_echoing_it(self):
        from mlflow_oidc_auth.session.token_vault import validate_encryption_key

        bad = "definitely-not-a-fernet-key-value"
        with pytest.raises(ValueError) as excinfo:
            validate_encryption_key(f"{Fernet.generate_key().decode()},{bad}")
        assert "SESSION_TOKEN_ENCRYPTION_KEY" in str(excinfo.value)
        assert "entry 1" in str(excinfo.value)
        assert bad not in str(excinfo.value)

    def test_config_load_fails_fast_on_a_malformed_key(self, monkeypatch):
        from mlflow_oidc_auth.config import AppConfig

        bad = "definitely-not-a-fernet-key-value"
        monkeypatch.setenv("SESSION_TOKEN_ENCRYPTION_KEY", bad)
        with pytest.raises(ValueError) as excinfo:
            AppConfig()
        assert bad not in str(excinfo.value)

    def test_config_load_accepts_a_valid_key(self, monkeypatch):
        from mlflow_oidc_auth.config import AppConfig

        key = Fernet.generate_key().decode()
        monkeypatch.setenv("SESSION_TOKEN_ENCRYPTION_KEY", key)
        assert AppConfig().SESSION_TOKEN_ENCRYPTION_KEY == key
