"""
Unit tests for configuration providers.

Tests the pluggable configuration provider system including:
- Base provider interface
- Environment variable provider
- Config manager chain of responsibility
- Provider priority and fallback behavior
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from mlflow_oidc_auth.config_providers.base import (
    ConfigProvider,
    SecretLevel,
    get_secret_level,
)
from mlflow_oidc_auth.config_providers.env_provider import EnvProvider
from mlflow_oidc_auth.config_providers.manager import ConfigManager


class TestSecretLevel(unittest.TestCase):
    """Tests for secret level classification."""

    def test_secret_keys_classified_as_secret(self) -> None:
        """Verify that sensitive keys are classified as SECRET."""
        self.assertEqual(get_secret_level("SECRET_KEY"), SecretLevel.SECRET)
        self.assertEqual(get_secret_level("OIDC_CLIENT_SECRET"), SecretLevel.SECRET)

    def test_sensitive_keys_classified_as_sensitive(self) -> None:
        """Verify that sensitive config keys are classified correctly."""
        self.assertEqual(get_secret_level("OIDC_USERS_DB_URI"), SecretLevel.SENSITIVE)
        self.assertEqual(get_secret_level("OIDC_CLIENT_ID"), SecretLevel.SENSITIVE)

    def test_unknown_keys_classified_as_public(self) -> None:
        """Verify that unknown keys default to PUBLIC."""
        self.assertEqual(get_secret_level("UNKNOWN_KEY"), SecretLevel.PUBLIC)
        self.assertEqual(get_secret_level("EXTEND_MLFLOW_MENU"), SecretLevel.PUBLIC)


class TestEnvProvider(unittest.TestCase):
    """Tests for the environment variable provider."""

    def setUp(self) -> None:
        self.provider = EnvProvider()

    def test_name(self) -> None:
        """Verify provider name."""
        self.assertEqual(self.provider.name, "env")

    def test_priority(self) -> None:
        """Verify env provider has lowest priority."""
        self.assertEqual(self.provider.priority, 1000)

    def test_is_available(self) -> None:
        """Env provider is always available."""
        self.assertTrue(self.provider.is_available())

    def test_get_existing_variable(self) -> None:
        """Get an existing environment variable."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            self.assertEqual(self.provider.get("TEST_VAR"), "test_value")

    def test_get_missing_variable_returns_default(self) -> None:
        """Missing variable returns default."""
        self.assertEqual(self.provider.get("NONEXISTENT_VAR", "default"), "default")

    def test_get_missing_variable_returns_none(self) -> None:
        """Missing variable without default returns None."""
        self.assertIsNone(self.provider.get("NONEXISTENT_VAR"))

    def test_get_many(self) -> None:
        """Get multiple variables at once."""
        with patch.dict(os.environ, {"VAR1": "value1", "VAR2": "value2"}):
            result = self.provider.get_many(["VAR1", "VAR2", "VAR3"])
            self.assertEqual(result, {"VAR1": "value1", "VAR2": "value2"})


class MockSecretProvider(ConfigProvider):
    """Mock provider for testing that handles secrets."""

    def __init__(self, secrets: dict) -> None:
        self._secrets = secrets

    @property
    def name(self) -> str:
        return "mock-secrets"

    @property
    def priority(self) -> int:
        return 10

    def is_available(self) -> bool:
        return True

    def get(self, key: str, default=None):
        level = get_secret_level(key)
        if level == SecretLevel.PUBLIC:
            return default
        return self._secrets.get(key, default)


class MockConfigProvider(ConfigProvider):
    """Mock provider for testing that handles config values."""

    def __init__(self, config: dict, priority: int = 50) -> None:
        self._config = config
        self._priority = priority

    @property
    def name(self) -> str:
        return "mock-config"

    @property
    def priority(self) -> int:
        return self._priority

    def is_available(self) -> bool:
        return True

    def get(self, key: str, default=None):
        return self._config.get(key, default)


class TestConfigManager(unittest.TestCase):
    """Tests for the ConfigManager."""

    def test_provider_priority_order(self) -> None:
        """Verify providers are sorted by priority."""
        manager = ConfigManager(auto_discover=False)

        provider1 = MockConfigProvider({}, priority=100)
        provider2 = MockSecretProvider({})
        # MockSecretProvider has priority 10

        manager.register_provider(provider1)
        manager.register_provider(provider2)

        # Lower priority number = higher priority
        self.assertEqual(manager.providers[0].name, "mock-secrets")
        self.assertEqual(manager.providers[1].name, "mock-config")

    def test_chain_of_responsibility(self) -> None:
        """First provider with value wins."""
        manager = ConfigManager(auto_discover=False)

        secret_provider = MockSecretProvider({"OIDC_CLIENT_SECRET": "secret_value"})
        config_provider = MockConfigProvider({"SOME_CONFIG": "config_value", "OIDC_CLIENT_SECRET": "wrong_value"})
        env_provider = EnvProvider()

        manager.register_provider(secret_provider)
        manager.register_provider(config_provider)
        manager.register_provider(env_provider)

        # Secret comes from secret provider
        self.assertEqual(manager.get("OIDC_CLIENT_SECRET"), "secret_value")
        # Config comes from config provider
        self.assertEqual(manager.get("SOME_CONFIG"), "config_value")

    def test_fallback_to_default(self) -> None:
        """Returns default when no provider has the value."""
        manager = ConfigManager(auto_discover=False)
        manager.register_provider(EnvProvider())

        self.assertEqual(manager.get("NONEXISTENT", "default_value"), "default_value")

    def test_get_bool(self) -> None:
        """Test boolean value parsing."""
        manager = ConfigManager(auto_discover=False)
        manager.register_provider(MockConfigProvider({"TRUE_VAL": "true", "FALSE_VAL": "false", "ONE_VAL": "1", "T_VAL": "T"}))

        self.assertTrue(manager.get_bool("TRUE_VAL"))
        self.assertFalse(manager.get_bool("FALSE_VAL"))
        self.assertTrue(manager.get_bool("ONE_VAL"))
        self.assertTrue(manager.get_bool("T_VAL"))
        self.assertFalse(manager.get_bool("NONEXISTENT"))
        self.assertTrue(manager.get_bool("NONEXISTENT", default=True))

    def test_get_int(self) -> None:
        """Test integer value parsing."""
        manager = ConfigManager(auto_discover=False)
        manager.register_provider(MockConfigProvider({"NUM": "42", "INVALID": "not_a_number"}))

        self.assertEqual(manager.get_int("NUM"), 42)
        self.assertEqual(manager.get_int("INVALID", default=0), 0)
        self.assertEqual(manager.get_int("NONEXISTENT", default=100), 100)

    def test_get_list(self) -> None:
        """Test list value parsing."""
        manager = ConfigManager(auto_discover=False)
        manager.register_provider(MockConfigProvider({"LIST": "a, b, c", "SINGLE": "only_one"}))

        self.assertEqual(manager.get_list("LIST"), ["a", "b", "c"])
        self.assertEqual(manager.get_list("SINGLE"), ["only_one"])
        self.assertEqual(manager.get_list("NONEXISTENT", default=["default"]), ["default"])

    def test_refresh_calls_all_providers(self) -> None:
        """Refresh should call refresh on all providers."""
        manager = ConfigManager(auto_discover=False)

        mock_provider = MockConfigProvider({})
        mock_provider.refresh = MagicMock()

        manager.register_provider(mock_provider)
        manager.refresh()

        mock_provider.refresh.assert_called_once()

    def test_close_calls_all_providers(self) -> None:
        """Close should call close on all providers."""
        manager = ConfigManager(auto_discover=False)

        mock_provider = MockConfigProvider({})
        mock_provider.close = MagicMock()

        manager.register_provider(mock_provider)
        manager.close()

        mock_provider.close.assert_called_once()


class TestKubernetesSecretsProvider(unittest.TestCase):
    """Tests for Kubernetes Secrets provider."""

    def test_reads_secrets_from_mounted_files(self) -> None:
        """Verify secrets are read from mounted files."""
        from mlflow_oidc_auth.config_providers.kubernetes_provider import (
            KubernetesSecretsProvider,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock secret files
            secret_path = Path(tmpdir)
            (secret_path / "OIDC_CLIENT_SECRET").write_text("my_secret_value")
            (secret_path / "SECRET_KEY").write_text("session_key\n")  # With trailing newline

            with patch.dict(
                os.environ,
                {
                    "CONFIG_K8S_SECRETS_ENABLED": "true",
                    "CONFIG_K8S_SECRETS_PATH": tmpdir,
                },
            ):
                provider = KubernetesSecretsProvider()
                self.assertTrue(provider.is_available())

                # Should read and strip newlines
                self.assertEqual(provider.get("OIDC_CLIENT_SECRET"), "my_secret_value")
                self.assertEqual(provider.get("SECRET_KEY"), "session_key")

                # Public keys should return default
                self.assertIsNone(provider.get("EXTEND_MLFLOW_MENU"))

    def test_not_available_when_disabled(self) -> None:
        """Provider is not available when not enabled."""
        from mlflow_oidc_auth.config_providers.kubernetes_provider import (
            KubernetesSecretsProvider,
        )

        with patch.dict(os.environ, {"CONFIG_K8S_SECRETS_ENABLED": "false"}, clear=False):
            provider = KubernetesSecretsProvider()
            self.assertFalse(provider.is_available())


class TestAWSProvidersAvailability(unittest.TestCase):
    """Tests for AWS provider availability checks."""

    def test_secrets_manager_not_available_when_disabled(self) -> None:
        """AWS Secrets Manager is not available when not enabled."""
        from mlflow_oidc_auth.config_providers.aws_secrets_provider import (
            AWSSecretsManagerProvider,
        )

        with patch.dict(os.environ, {"CONFIG_AWS_SECRETS_ENABLED": "false"}, clear=False):
            provider = AWSSecretsManagerProvider()
            self.assertFalse(provider.is_available())

    def test_parameter_store_not_available_when_disabled(self) -> None:
        """AWS Parameter Store is not available when not enabled."""
        from mlflow_oidc_auth.config_providers.aws_parameter_store_provider import (
            AWSParameterStoreProvider,
        )

        with patch.dict(os.environ, {"CONFIG_AWS_PARAMETER_STORE_ENABLED": "false"}, clear=False):
            provider = AWSParameterStoreProvider()
            self.assertFalse(provider.is_available())


class TestAzureProviderAvailability(unittest.TestCase):
    """Tests for Azure provider availability checks."""

    def test_keyvault_not_available_when_disabled(self) -> None:
        """Azure Key Vault is not available when not enabled."""
        from mlflow_oidc_auth.config_providers.azure_keyvault_provider import (
            AzureKeyVaultProvider,
        )

        with patch.dict(os.environ, {"CONFIG_AZURE_KEYVAULT_ENABLED": "false"}, clear=False):
            provider = AzureKeyVaultProvider()
            self.assertFalse(provider.is_available())

    def test_keyvault_not_available_without_vault_name(self) -> None:
        """Azure Key Vault requires vault name."""
        from mlflow_oidc_auth.config_providers.azure_keyvault_provider import (
            AzureKeyVaultProvider,
        )

        with patch.dict(
            os.environ,
            {"CONFIG_AZURE_KEYVAULT_ENABLED": "true", "CONFIG_AZURE_KEYVAULT_NAME": ""},
            clear=False,
        ):
            provider = AzureKeyVaultProvider()
            self.assertFalse(provider.is_available())


class TestVaultProviderAvailability(unittest.TestCase):
    """Tests for HashiCorp Vault provider availability checks."""

    def test_vault_not_available_when_disabled(self) -> None:
        """HashiCorp Vault is not available when not enabled."""
        from mlflow_oidc_auth.config_providers.vault_provider import (
            HashiCorpVaultProvider,
        )

        with patch.dict(os.environ, {"CONFIG_VAULT_ENABLED": "false"}, clear=False):
            provider = HashiCorpVaultProvider()
            self.assertFalse(provider.is_available())

    def test_vault_not_available_without_auth(self) -> None:
        """HashiCorp Vault requires authentication credentials."""
        from mlflow_oidc_auth.config_providers.vault_provider import (
            HashiCorpVaultProvider,
        )

        with patch.dict(
            os.environ,
            {
                "CONFIG_VAULT_ENABLED": "true",
                "CONFIG_VAULT_TOKEN": "",
                "CONFIG_VAULT_ROLE_ID": "",
                "CONFIG_VAULT_SECRET_ID": "",
            },
            clear=False,
        ):
            provider = HashiCorpVaultProvider()
            self.assertFalse(provider.is_available())


if __name__ == "__main__":
    unittest.main()
