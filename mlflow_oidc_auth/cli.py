"""
CLI entry point for MLflow OIDC Auth server with cloud configuration support.

This module provides a `mlflow-oidc-server` command that:
1. Loads configuration from cloud providers (AWS Secrets Manager, Azure Key Vault, etc.)
2. Sets environment variables for MLflow
3. Executes `mlflow server` with the configured environment

Usage:
    mlflow-oidc-server --host 0.0.0.0 --port 8080

This is more elegant than subprocess as it uses os.execvp to replace the
current process with mlflow, which is the standard pattern for container
entrypoints.
"""

import os
import sys
from typing import NoReturn

import click

from mlflow_oidc_auth.config_providers.mlflow_env import configure_mlflow_environment, get_mlflow_config_summary
from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


@click.command(
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option(
    "--show-config",
    is_flag=True,
    default=False,
    help="Show resolved configuration (secrets masked) and exit.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show the mlflow command that would be executed without running it.",
)
@click.pass_context
def main(ctx: click.Context, show_config: bool, dry_run: bool) -> NoReturn | None:
    """MLflow OIDC Auth Server with cloud configuration support.

    Loads configuration from cloud providers (AWS Secrets Manager, Azure Key Vault,
    HashiCorp Vault, Kubernetes Secrets) and starts the MLflow server.

    All additional arguments are passed directly to `mlflow server`.

    Examples:

        # Start server with cloud config
        mlflow-oidc-server --host 0.0.0.0 --port 8080

        # Show resolved configuration
        mlflow-oidc-server --show-config

        # Dry run to see what would be executed
        mlflow-oidc-server --dry-run --host 0.0.0.0 --port 8080

        # Pass any mlflow server options
        mlflow-oidc-server --workers 4 --artifacts-destination s3://bucket/
    """
    # Load configuration from providers into environment
    logger.info("Loading configuration from providers...")
    configured = configure_mlflow_environment()

    if configured:
        logger.info(f"Loaded {len(configured)} configuration values from providers")
    else:
        logger.info("No additional configuration loaded from providers (using environment)")

    if show_config:
        click.echo("\nResolved MLflow Configuration:")
        click.echo("-" * 40)
        summary = get_mlflow_config_summary()
        if summary:
            for key, value in sorted(summary.items()):
                click.echo(f"  {key}={value}")
        else:
            click.echo("  (no MLflow environment variables set)")
        click.echo()
        return

    # Build mlflow command
    mlflow_args = ["mlflow", "server", "--app-name", "oidc-auth"]
    mlflow_args.extend(ctx.args)

    if dry_run:
        click.echo("\nWould execute:")
        click.echo(f"  {' '.join(mlflow_args)}")
        click.echo("\nWith environment variables:")
        summary = get_mlflow_config_summary()
        for key, value in sorted(summary.items()):
            click.echo(f"  {key}={value}")
        return

    logger.info(f"Starting MLflow server: {' '.join(mlflow_args)}")

    # Use execvp to replace current process with mlflow
    # This is the standard container entrypoint pattern - no subprocess overhead
    os.execvp("mlflow", mlflow_args)


def run() -> None:
    """Entry point wrapper for setuptools console_scripts."""
    main()


if __name__ == "__main__":
    run()
