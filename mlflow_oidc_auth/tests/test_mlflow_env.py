"""Tests for configure_mlflow_environment logging."""

import logging
from unittest.mock import patch

from mlflow_oidc_auth.config_providers import mlflow_env

FTP_ROOT = "ftp://svc:ftp-s3cr3t@files.example.com/artifacts"
DB_URI = "postgresql://svc:db-s3cr3t@db.example.com/mlflow"


def test_configured_values_are_not_logged(monkeypatch, caplog):
    """Only variable names are logged; no value (classified secret or not) reaches the log."""
    values = {"MLFLOW_DEFAULT_ARTIFACT_ROOT": FTP_ROOT, "MLFLOW_BACKEND_STORE_URI": DB_URI}
    for env_var in mlflow_env.MLFLOW_ENV_MAPPINGS.values():
        monkeypatch.delenv(env_var, raising=False)

    with patch.object(mlflow_env.config_manager, "get", side_effect=values.get), caplog.at_level(logging.DEBUG):
        configured = mlflow_env.configure_mlflow_environment()

    assert configured == values
    assert "Configured MLFLOW_DEFAULT_ARTIFACT_ROOT from provider" in caplog.text
    assert "Configured MLFLOW_BACKEND_STORE_URI from provider" in caplog.text
    assert "ftp-s3cr3t" not in caplog.text
    assert "db-s3cr3t" not in caplog.text


def test_summary_masks_uri_passwords_in_unclassified_values(monkeypatch):
    """--show-config / --dry-run output keeps the URI but masks its password."""
    monkeypatch.setenv("MLFLOW_DEFAULT_ARTIFACT_ROOT", FTP_ROOT)
    monkeypatch.setenv("MLFLOW_BACKEND_STORE_URI", DB_URI)

    summary = mlflow_env.get_mlflow_config_summary()

    assert summary["MLFLOW_DEFAULT_ARTIFACT_ROOT"] == "ftp://svc:********@files.example.com/artifacts"
    assert summary["MLFLOW_BACKEND_STORE_URI"] == "********"


def test_redact_uri_passwords():
    """Passwords are masked wherever a URI appears; URIs without one are unchanged."""
    text = f"--backend-store-uri {DB_URI} --artifacts-destination s3://bucket/path --x redis://:pw@h:6379/0"
    redacted = mlflow_env.redact_uri_passwords(text)
    assert "db-s3cr3t" not in redacted
    assert ":pw@" not in redacted
    assert "postgresql://svc:********@db.example.com/mlflow" in redacted
    assert "s3://bucket/path" in redacted
    assert "redis://:********@h:6379/0" in redacted
    assert mlflow_env.redact_uri_passwords("https://user@example.com/x") == "https://user@example.com/x"


def test_cli_dry_run_masks_uri_passwords(monkeypatch):
    """mlflow-oidc-server --dry-run echoes the command with URI passwords masked."""
    from click.testing import CliRunner

    from mlflow_oidc_auth import cli

    monkeypatch.setattr(cli, "configure_mlflow_environment", lambda: {})
    result = CliRunner().invoke(cli.main, ["--dry-run", "--backend-store-uri", DB_URI])

    assert result.exit_code == 0, result.output
    assert "postgresql://svc:********@db.example.com/mlflow" in result.output
    assert "db-s3cr3t" not in result.output
