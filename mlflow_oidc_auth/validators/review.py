"""Validators for MLflow label schemas and review queues (human review of traces).

Both are scoped to an experiment and inherit its permission: READ for reads, UPDATE for
writes, DELETE for deleting a schema or a queue. Routes that name the experiment directly
(create, get-by-name, list) use the experiment validators; the ones here resolve a schema or
queue id to its experiment first.

A label schema normally carries its experiment id. One that does not is readable by any
authenticated user and writable only by an admin.

A personal queue may be created for another user (the UI assigns work this way), but only
for an existing, active, non-service account. ``completed_by`` on an item records who did
the review, so it must be the caller.
"""

from __future__ import annotations

from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import NO_PERMISSIONS, READ, Permission, intersect_permissions
from mlflow_oidc_auth.utils import all_source_values, get_request_param_values
from mlflow_oidc_auth.validators._experiment_scope import names_only_caller, permission_on_all_experiments
from mlflow_oidc_auth.validators.experiment import validate_can_update_experiment

# ---------------------------------------------------------------------------
# Label schemas
# ---------------------------------------------------------------------------


def _label_schema_permission(username: str, *, unscoped: Permission) -> Permission:
    tracking_store = _get_tracking_store()
    permissions = []
    for schema_id in get_request_param_values("schema_id"):
        experiment_id = tracking_store.get_label_schema(str(schema_id)).experiment_id
        permissions.append(unscoped if not experiment_id else permission_on_all_experiments([experiment_id], username))
    return intersect_permissions(permissions)


def validate_can_read_label_schema(username: str) -> bool:
    """READ on the schema's experiment; any authenticated user for a schema with none."""
    return _label_schema_permission(username, unscoped=READ).can_read


def validate_can_update_label_schema(username: str) -> bool:
    """UPDATE on the schema's experiment; admin-only for a schema with none."""
    return _label_schema_permission(username, unscoped=NO_PERMISSIONS).can_update


def validate_can_delete_label_schema(username: str) -> bool:
    """DELETE on the schema's experiment; admin-only for a schema with none."""
    return _label_schema_permission(username, unscoped=NO_PERMISSIONS).can_delete


# ---------------------------------------------------------------------------
# Review queues
# ---------------------------------------------------------------------------


def _review_queue_permission(username: str) -> Permission:
    tracking_store = _get_tracking_store()
    experiment_ids = [tracking_store.get_review_queue(str(queue_id)).experiment_id for queue_id in get_request_param_values("queue_id")]
    return permission_on_all_experiments(experiment_ids, username)


def _is_assignable_user(name: str) -> bool:
    """True if ``name`` is an existing, active user account that is not a service account."""
    from mlflow.exceptions import MlflowException

    from mlflow_oidc_auth.store import store

    try:
        user = store.get_user_profile(str(name).strip())
    except MlflowException:
        return False
    return bool(user.active) and not user.is_service_account


def validate_can_get_or_create_user_queue(username: str) -> bool:
    """UPDATE on the experiment; the queue's ``user`` must be an active, non-service account.

    MLflow's UI calls this with the ASSIGNEE as ``user`` when it routes a trace to a
    teammate, so the user need not be the caller. It must name a real person, though, so a
    queue cannot be created for an arbitrary string.
    """
    return all(_is_assignable_user(name) for name in all_source_values("user")) and validate_can_update_experiment(username)


def validate_can_read_review_queue(username: str) -> bool:
    """READ on the queue's experiment (get, items/list)."""
    return _review_queue_permission(username).can_read


def validate_can_update_review_queue(username: str) -> bool:
    """UPDATE on the queue's experiment; MANAGE to hand the queue to a new owner."""
    permission = _review_queue_permission(username)
    if all_source_values("new_owner"):
        return permission.can_manage
    return permission.can_update


def validate_can_delete_review_queue(username: str) -> bool:
    """DELETE on the queue's experiment."""
    return _review_queue_permission(username).can_delete


def validate_can_update_review_queue_items(username: str) -> bool:
    """UPDATE on the queue's experiment (items/add, items/remove)."""
    return _review_queue_permission(username).can_update


# ReviewStatus.PENDING, by name or by proto number.
_PENDING_STATUS = {"PENDING", "1"}


def validate_can_set_review_queue_item_status(username: str) -> bool:
    """UPDATE on the queue's experiment; ``completed_by`` must be the caller, and is required
    when the item moves to a terminal state."""
    if not names_only_caller("completed_by", username):
        return False
    # Moving an item to a terminal state (COMPLETE / DECLINED) records who reviewed it, so
    # the caller must be named; MLflow's UI and client always send it there.
    statuses = {str(s).strip().upper() for s in all_source_values("status")}
    if statuses - _PENDING_STATUS and not all_source_values("completed_by"):
        return False
    return _review_queue_permission(username).can_update
