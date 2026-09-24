"""Validators for MLflow label schemas and review queues (human review of traces).

Both are scoped to an experiment and inherit its permission: READ for reads, UPDATE for
writes, DELETE for deleting a schema or a queue. Routes that name the experiment directly
(create, get-by-name, list) use the experiment validators; the ones here resolve a schema or
queue id to its experiment first.

A label schema normally carries its experiment id. One that does not is readable by any
authenticated user and writable only by an admin.

MLflow attributes review work to the user a request names (``user`` on a personal queue,
``completed_by`` on an item). Those must be the caller: naming someone else is refused.
"""

from __future__ import annotations

from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.permissions import NO_PERMISSIONS, READ, Permission, intersect_permissions
from mlflow_oidc_auth.utils import all_source_values, get_request_param_values
from mlflow_oidc_auth.validators._experiment_scope import permission_on_all_experiments
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


def _names_only_caller(param: str, username: str) -> bool:
    """True if every value of ``param`` in the request is ``username`` (MLflow lower-cases users)."""
    caller = username.strip().lower()
    return all(str(value).strip().lower() == caller for value in all_source_values(param))


def validate_can_get_or_create_user_queue(username: str) -> bool:
    """UPDATE on the experiment, for the caller's own personal queue only."""
    return _names_only_caller("user", username) and validate_can_update_experiment(username)


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


def validate_can_set_review_queue_item_status(username: str) -> bool:
    """UPDATE on the queue's experiment; ``completed_by``, if given, must be the caller."""
    return _names_only_caller("completed_by", username) and _review_queue_permission(username).can_update
