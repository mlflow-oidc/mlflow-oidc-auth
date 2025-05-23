import secrets
import string

from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.store import store


def generate_token() -> str:
    alphabet = string.ascii_letters + string.digits
    new_password = "".join(secrets.choice(alphabet) for _ in range(24))
    return new_password


def create_user(username: str, display_name: str, is_admin: bool = False, is_service_account: bool = False) -> tuple:
    try:
        user = store.get_user(username)
        store.update_user(username=username, is_admin=is_admin, is_service_account=is_service_account)
        return False, f"User {user.username} (ID: {user.id}) already exists"
    except MlflowException:
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
