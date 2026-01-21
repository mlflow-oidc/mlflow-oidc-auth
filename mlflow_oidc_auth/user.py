import secrets
import string

from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.store import store

# Default token name for new users and backwards compatibility
DEFAULT_TOKEN_NAME = "default"


def generate_token() -> str:
    alphabet = string.ascii_letters + string.digits
    new_password = "".join(secrets.choice(alphabet) for _ in range(24))
    return new_password


def create_user(username: str, display_name: str, is_admin: bool = False, is_service_account: bool = False) -> tuple:
    try:
        user = store.get_user_profile(username)
        store.update_user(username=username, is_admin=is_admin, is_service_account=is_service_account)
        return False, f"User {user.username} (ID: {user.id}) already exists"
    except MlflowException:
        # Generate initial token
        token = generate_token()

        # Create user with placeholder password_hash (authentication uses tokens table)
        user = store.create_user(
            username=username,
            password=token,  # This goes to password_hash for backwards compat, but won't be used for auth
            display_name=display_name,
            is_admin=is_admin,
            is_service_account=is_service_account,
        )

        # Create the actual token in the tokens table (this is what's used for authentication)
        store.create_user_token(username=username, name=DEFAULT_TOKEN_NAME, token=token)

        return True, f"User {user.username} (ID: {user.id}) successfully created"


def populate_groups(group_names: list) -> None:
    store.populate_groups(group_names=group_names)


def update_user(username: str, group_names: list) -> None:
    store.set_user_groups(username, group_names)
