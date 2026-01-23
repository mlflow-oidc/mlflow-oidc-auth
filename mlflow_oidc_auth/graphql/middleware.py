from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Sequence

from mlflow.exceptions import MlflowException
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.bridge import get_fastapi_admin_status, get_fastapi_username
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.utils import effective_experiment_permission, effective_registered_model_permission

logger = get_logger()


@dataclass(frozen=True)
class _AuthContext:
    """Authentication context for a single request."""

    username: Optional[str]
    is_admin: bool


def _get_auth_context() -> _AuthContext:
    """Best-effort retrieval of auth context injected by FastAPI.

    MLflow serves `/graphql` from the Flask app. In this project, FastAPI performs
    authentication and injects auth info into the Flask WSGI environ.

    Returns:
        `_AuthContext` with `username` and `is_admin`.
    """

    try:
        username = get_fastapi_username()
    except Exception:
        username = None

    try:
        is_admin = get_fastapi_admin_status()
    except Exception:
        is_admin = False

    return _AuthContext(username=username, is_admin=is_admin)


def _get_input_obj(args: dict[str, Any]) -> Any:
    """Extract the conventional GraphQL `input` argument from resolver kwargs."""

    return args.get("input")


def _get_input_attr(input_obj: Any, name: str, default: Any = None) -> Any:
    """Read an attribute from an input object supporting both dict and attribute access."""

    if input_obj is None:
        return default
    if isinstance(input_obj, dict):
        return input_obj.get(name, default)
    return getattr(input_obj, name, default)


def _set_input_attr(input_obj: Any, name: str, value: Any) -> None:
    """Set an attribute on an input object supporting both dict and attribute access."""

    if input_obj is None:
        return
    if isinstance(input_obj, dict):
        input_obj[name] = value
        return
    setattr(input_obj, name, value)


def _can_read_experiment(experiment_id: str, username: str) -> bool:
    """Check READ access to an experiment for a user."""
    logger.debug(f"GraphQL checking READ access to experiment {experiment_id} for user {username}")
    return effective_experiment_permission(experiment_id, username).permission.can_read


def _can_read_run(run_id: str, username: str) -> bool:
    """Check READ access to a run for a user.

    Run permissions inherit from the parent experiment, so we resolve the run to
    its experiment and then apply experiment READ checks.
    """

    tracking_store = _get_tracking_store()
    run = tracking_store.get_run(run_id)
    return _can_read_experiment(run.info.experiment_id, username)


def _can_read_model(model_name: str, username: str) -> bool:
    """Check READ access to a registered model for a user."""
    logger.debug(f"GraphQL checking READ access to model {model_name} for user {username}")
    return effective_registered_model_permission(model_name, username).permission.can_read


def _extract_first_filter_value(filter_str: str, key: str) -> Optional[str]:
    """Best-effort extraction of a value from a simple `key = 'value'` filter.

    MLflow filter strings can be complex; for GraphQL authorization we only
    support a conservative subset (single equality / IN clauses).
    """

    # Supports: key='x', key = 'x', key = "x"
    m = re.search(rf"\b{re.escape(key)}\b\s*=\s*(['\"])(?P<val>[^'\"]+)\1", filter_str)
    if m:
        return m.group("val")

    # Supports: key IN ('a','b') or key in ("a", "b")
    m = re.search(rf"\b{re.escape(key)}\b\s+IN\s*\((?P<vals>[^)]+)\)", filter_str, flags=re.IGNORECASE)
    if m:
        raw_vals = m.group("vals")
        # Return the first value; we intentionally keep this conservative.
        for token in raw_vals.split(","):
            token = token.strip()
            if len(token) >= 2 and token[0] in "'\"" and token[-1] == token[0]:
                return token[1:-1]
    return None


class GraphQLAuthorizationMiddleware:
    """Graphene middleware enforcing per-field authorization for MLflow GraphQL.

    This mirrors the MLflow basic-auth behavior:
    - Only a limited set of GraphQL fields are protected.
    - Unauthorized access results in `null` fields rather than a REST 403.
    - For search-like fields, experiment ids are filtered to readable ones.

    The middleware relies on auth context injected by FastAPI into the Flask WSGI
    environ (via `mlflow_oidc_auth.bridge`).
    """

    PROTECTED_FIELDS: set[str] = {
        "mlflowGetExperiment",
        "mlflowGetRun",
        "mlflowListArtifacts",
        "mlflowGetMetricHistoryBulkInterval",
        "mlflowSearchRuns",
        "mlflowSearchDatasets",
        # Model registry related
        "mlflowSearchModelVersions",
        # Nested field on a run that resolves model versions.
        "modelVersions",
    }

    def resolve(self, next_: Callable[..., Any], root: Any, info: Any, **args: Any) -> Any:
        """Graphene middleware resolve hook."""

        field_name = getattr(info, "field_name", None)
        if not field_name or field_name not in self.PROTECTED_FIELDS:
            return next_(root, info, **args)

        auth = _get_auth_context()
        if auth.username is None:
            # Authentication should already be enforced by Flask before_request hook,
            # but keep this defensive to avoid leaking data if that changes.
            return None

        if auth.is_admin:
            return next_(root, info, **args)

        try:
            if not self._check_authorization(field_name, root, args, auth.username):
                logger.debug(f"GraphQL authorization denied for {field_name} by user {auth.username}")
                return None
        except MlflowException:
            # Match upstream behavior: fail closed, return null.
            return None
        except Exception:
            logger.warning("GraphQL authorization error", exc_info=True)
            return None

        return next_(root, info, **args)

    def _check_authorization(self, field_name: str, root: Any, args: dict[str, Any], username: str) -> bool:
        """Return True if the user is authorized for the requested GraphQL field."""

        input_obj = _get_input_obj(args)
        if input_obj is None:
            # No input means no specific resource to check.
            return True

        if field_name == "mlflowGetExperiment":
            experiment_id = _get_input_attr(input_obj, "experiment_id")
            return True if experiment_id is None else _can_read_experiment(str(experiment_id), username)

        if field_name in ("mlflowGetRun", "mlflowListArtifacts"):
            run_id = _get_input_attr(input_obj, "run_id") or _get_input_attr(input_obj, "run_uuid")
            return True if run_id is None else _can_read_run(str(run_id), username)

        if field_name == "mlflowGetMetricHistoryBulkInterval":
            run_ids: Sequence[str] = _get_input_attr(input_obj, "run_ids", []) or []
            for run_id in run_ids:
                if not _can_read_run(str(run_id), username):
                    return False
            return True

        if field_name in ("mlflowSearchRuns", "mlflowSearchDatasets"):
            experiment_ids: Sequence[str] = _get_input_attr(input_obj, "experiment_ids", []) or []
            readable_ids = [str(exp_id) for exp_id in experiment_ids if _can_read_experiment(str(exp_id), username)]
            if not readable_ids:
                return False
            _set_input_attr(input_obj, "experiment_ids", readable_ids)
            return True

        if field_name == "modelVersions":
            # Field is resolved on an MlflowRun object; permissions inherit from the
            # parent experiment (same as run read).
            experiment_id = getattr(getattr(root, "info", None), "experiment_id", None)
            return True if experiment_id is None else _can_read_experiment(str(experiment_id), username)

        if field_name == "mlflowSearchModelVersions":
            filter_str = _get_input_attr(input_obj, "filter") or _get_input_attr(input_obj, "filter_string")
            if not filter_str:
                return False

            # Try model-name based authorization first.
            if model_name := _extract_first_filter_value(str(filter_str), "name"):
                return _can_read_model(str(model_name), username)

            # If query is scoped by run_id, fall back to run-based authorization.
            if run_id := (_extract_first_filter_value(str(filter_str), "run_id") or _extract_first_filter_value(str(filter_str), "run_uuid")):
                return _can_read_run(str(run_id), username)

            # Unknown / complex filter: fail closed.
            return False

        # Unknown field (should not happen due to PROTECTED_FIELDS filtering).
        return True
