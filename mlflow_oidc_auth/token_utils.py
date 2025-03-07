import fnmatch

from mlflow_oidc_auth.config import config


def token_get_user_groups(token: dict) -> list[str]:
    """Retrieve the list of groups this user (based on the provided token) is a member of

    Args:
        token: dictionary holding the oidc token information

    Returns:
        list of all the groups this user is a member of
    """
    user_groups = []

    if config.OIDC_GROUP_DETECTION_PLUGIN:
        import importlib

        user_groups = importlib.import_module(config.OIDC_GROUP_DETECTION_PLUGIN).get_user_groups(token["access_token"])
    else:
        user_groups = token["userinfo"][config.OIDC_GROUPS_ATTRIBUTE]

    # Now filter the user groups to keep only those matching the pattern or the ADMIN group
    user_groups = sorted(
        set(
            [
                g
                for g in user_groups
                if (g == config.OIDC_ADMIN_GROUP_NAME) or any(fnmatch.fnmatch(g, p) for p in config.OIDC_GROUP_FILTER_PATTERNS)
            ]
        )
    )

    return user_groups


def token_get_user_is_admin(user_groups: list[str]):
    """Check if the admin group is included in the user_groups. In that case
    it means that the user is an admin user

    Args:
        user_groups (list[str]): list of the groups the current user belongs to

    Returns:
        True if the admin group is in the list of the groups of the current user, False otherwise

    """
    is_admin = False

    if config.OIDC_ADMIN_GROUP_NAME in user_groups:
        is_admin = True

    return is_admin
