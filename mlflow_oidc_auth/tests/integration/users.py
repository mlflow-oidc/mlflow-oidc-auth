# Users and groups as defined in the OIDC mock provider:
# https://oidc-mock.technicaldomain.xyz/
USERS = [
    (
        "alice@example.com",
        ["mlflow-users", "experiments-reader", "prompts-reader", "models-reader"],
    ),
    (
        "bob@example.com",
        ["mlflow-users", "experiments-editor", "prompts-editor", "models-editor"],
    ),
    (
        "charlie@example.com",
        ["mlflow-users", "experiments-manager", "prompts-manager", "models-manager"],
    ),
    (
        "dave@example.com",
        [
            "mlflow-users",
            "experiments-no-access",
            "prompts-no-access",
            "models-no-access",
        ],
    ),
    (
        "eve@example.com",
        ["mlflow-users"],
    ),  # Only mlflow-users, uses default permissions
    ("frank@example.com", ["mlflow-admin"]),  # Administrator
    ("peter@example.com", ["random-group"]),  # Not in mlflow-users group
]


def list_users() -> list[str]:
    """
    Returns a list of user emails
    """
    return [user[0] for user in USERS]


def list_groups() -> list[str]:
    """
    Returns a list of groups
    """
    return [group for user in USERS for group in user[1]]


def get_user_groups(email: str) -> list[str]:
    """
    Returns a list of groups for a specific user
    """
    for user in USERS:
        if user[0] == email:
            return list(user[1])
    return []


def get_mlflow_users() -> list[str]:
    """
    Returns a list of user emails who are members of mlflow-users group
    """
    return [user[0] for user in USERS if "mlflow-users" in user[1]]


def get_admin_users() -> list[str]:
    """
    Returns a list of user emails who are members of mlflow-admin group
    """
    return [user[0] for user in USERS if "mlflow-admin" in user[1]]


def get_non_mlflow_users() -> list[str]:
    """
    Returns a list of user emails who are NOT members of mlflow-users or mlflow-admin groups
    """
    return [user[0] for user in USERS if "mlflow-users" not in user[1] and "mlflow-admin" not in user[1]]


EXPERIMENTS = [
    "personal-experiment",
    "group-experiment",
    "regexp-personal-experiment",
    "regexp-group-experiment",
]

MODELS = [
    "personal-model",
    "group-model",
    "regexp-personal-model",
    "regexp-group-model",
]

PROMPTS = [
    "personal-prompt",
    "group-prompt",
    "regexp-personal-prompt",
    "regexp-group-prompt",
]


def list_experiments() -> list[str]:
    """
    Returns a list of experiment names
    """
    return EXPERIMENTS


def list_models() -> list[str]:
    """
    Returns a list of model names
    """
    return MODELS


def list_prompts() -> list[str]:
    """
    Returns a list of prompt names
    """
    return PROMPTS
