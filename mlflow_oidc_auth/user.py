import secrets
import string
from datetime import datetime, timedelta, timezone

from typing import Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode

from mlflow_oidc_auth.store import store

# Default token name for new users and backwards compatibility
DEFAULT_TOKEN_NAME = "default"


def generate_token() -> str:
    alphabet = string.ascii_letters + string.digits
    new_password = "".join(secrets.choice(alphabet) for _ in range(24))
    return new_password


def create_user(
    username: str,
    display_name: str,
    is_admin: bool = False,
    is_service_account: bool = False,
    written_by: Optional[str] = None,
    admin_override: bool = False,
) -> tuple:
    """Create or refresh a user record.

    ``written_by`` names the source performing the write, for the ownership guard (#319). Without
    it every write looks like ``manual``, so under ``enforce`` a directory's own sync would be
    refused on the rows it owns — the guard would lock out precisely the users it exists to
    protect.
    """
    try:
        user = store.get_user_profile(username)
        store.update_user(
            username=username,
            is_admin=is_admin,
            is_service_account=is_service_account,
            written_by=written_by,
            admin_override=admin_override,
        )
        return False, f"User {user.username} (ID: {user.id}) already exists"
    except MlflowException as exc:
        # Only "there is no such user" means "go create them". Every other refusal — an
        # ownership conflict (#319), the last-active-admin guard, a validation error — is a real
        # answer, and falling through to create would re-report it as RESOURCE_ALREADY_EXISTS
        # with the actual reason left in the log. Keyed on the error code rather than the
        # message, so rewording an exception cannot quietly restore that.
        if exc.error_code != ErrorCode.Name(RESOURCE_DOES_NOT_EXIST):
            raise
        # Generate initial token
        token = generate_token()

        # Create user (no password stored on users table - authentication uses tokens table)
        user = store.create_user(
            username=username,
            display_name=display_name,
            is_admin=is_admin,
            is_service_account=is_service_account,
            written_by=written_by,
            admin_override=admin_override,
        )

        # Create the token in the tokens table (this is what's used for authentication)
        # Default expiration is 1 year from now
        default_expiration = datetime.now(timezone.utc) + timedelta(days=365)
        store.create_user_token(username=username, name=DEFAULT_TOKEN_NAME, token=token, expires_at=default_expiration)

        return True, f"User {user.username} (ID: {user.id}) successfully created"


def populate_groups(group_names: list) -> None:
    store.populate_groups(group_names=group_names)


def update_user(username: str, group_names: list) -> None:
    store.set_user_groups(username, group_names)
