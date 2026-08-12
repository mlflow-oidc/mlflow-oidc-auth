import secrets
import string

from typing import Optional

from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.store import store


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
        if "is managed by" in str(exc):
            # An ownership refusal is not "this user does not exist" — creating them instead
            # would report RESOURCE_ALREADY_EXISTS and bury the real reason.
            raise
        password = generate_token()
        user = store.create_user(
            username=username,
            password=password,
            display_name=display_name,
            is_admin=is_admin,
            is_service_account=is_service_account,
        )
        return True, f"User {user.username} (ID: {user.id}) successfully created"


def populate_groups(group_names: list) -> None:
    store.populate_groups(group_names=group_names)


def update_user(username: str, group_names: list) -> None:
    store.set_user_groups(username, group_names)
