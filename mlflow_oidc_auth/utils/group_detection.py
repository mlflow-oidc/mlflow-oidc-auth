"""Invoke ``OIDC_GROUP_DETECTION_PLUGIN`` plugins.

Plugins were originally called as ``get_user_groups(access_token)``. Issue #250 asks for the full
token response to also be available, without breaking plugins already deployed against the old
signature. A plugin opts in by declaring a ``token_response`` parameter (positional-or-keyword,
keyword-only, or via ``**kwargs``); anything else is called exactly as before.
"""

import functools
import importlib
import inspect
from typing import Any, Callable, Dict

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


@functools.lru_cache(maxsize=None)
def _accepts_token_response(get_user_groups: Callable) -> bool:
    """Whether ``get_user_groups`` accepts a ``token_response`` keyword argument.

    Cached per function object: ``inspect.signature`` runs on every interactive login and every
    bearer-authenticated request, so the introspection is done once per plugin callable rather
    than on every call.
    """
    try:
        signature = inspect.signature(get_user_groups)
    except (TypeError, ValueError):
        # Builtins and some C-implemented callables have no inspectable signature. Fall back to
        # the pre-existing, single-argument call.
        return False

    for parameter in signature.parameters.values():
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            return True
        if parameter.name == "token_response" and parameter.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            return True
    return False


def _plugin_accepts_token_response(get_user_groups: Callable) -> bool:
    """``_accepts_token_response`` for any callable, including unhashable ones.

    A plugin may expose ``get_user_groups`` as a callable object that defines ``__eq__`` without
    ``__hash__``. Such an object cannot be an ``lru_cache`` key, so it is introspected uncached
    rather than failing every login.
    """
    try:
        return _accepts_token_response(get_user_groups)
    except TypeError:
        return _accepts_token_response.__wrapped__(get_user_groups)


def call_group_detection_plugin(plugin_path: str, access_token: str, token_response: Dict[str, Any]) -> Any:
    """Call the configured group-detection plugin, passing the token response when it accepts one.

    Backward compatible: a plugin whose ``get_user_groups`` only takes the access token is called
    exactly as before. A plugin that declares a ``token_response`` parameter (or ``**kwargs``)
    additionally receives it as a keyword argument.

    Never logs ``token_response`` — it may carry an access token, an ID token, or user claims.

    Args:
        plugin_path: The ``OIDC_GROUP_DETECTION_PLUGIN`` module path.
        access_token: The access/bearer token, passed positionally exactly as before.
        token_response: The full token response (interactive login) or, on the bearer path, a
            dict carrying at least ``access_token`` plus the validated claims under a clear key.

    Returns:
        Whatever the plugin's ``get_user_groups`` returns.
    """
    get_user_groups = importlib.import_module(plugin_path).get_user_groups
    if _plugin_accepts_token_response(get_user_groups):
        return get_user_groups(access_token, token_response=token_response)
    return get_user_groups(access_token)
