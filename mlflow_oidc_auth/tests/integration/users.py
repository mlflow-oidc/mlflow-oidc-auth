USERS = [
    ("alice@example.com", ["mlflow-users", "experiments-reader", "prompts-reader", "models-reader"]),
    ("bob@example.com", ["mlflow-users", "experiments-editor", "prompts-editor", "models-editor"]),
    ("charlie@example.com", ["mlflow-users", "experiments-manager", "prompts-manager", "models-manager"]),
    ("dave@example.com", ["mlflow-users", "experiments-no-access", "prompts-no-access", "models-no-access"]),
    ("eve@example.com", ["mlflow-users", "experiments-no-access", "prompts-no-access", "models-no-access"]),
    ("frank@example.com", ["mlflow-admin"]),
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
            return user[1]
    return []


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
