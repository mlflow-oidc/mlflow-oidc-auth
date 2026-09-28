"""Validators for MLflow label schemas and review queues (human review of traces).

Both are scoped to an experiment and inherit its permission. The rules follow MLflow's own
auth plugin (``mlflow.server.auth``), in this plugin's permission names (MLflow's ``EDIT`` is
our ``can_update``):

Label schemas
    READ on the experiment to read; MANAGE to create, update or delete. A label schema
    normally carries its experiment id. One that does not is readable by any authenticated
    user and writable only by an admin.

Review queues
    * create: EDIT on the experiment (the creator becomes the queue's owner).
    * view (get, get-by-name, items/list): READ on the experiment and one of MANAGE, being
      an assigned user of the queue, or EDIT plus owning the queue.
    * update: MANAGE, or EDIT plus owning the queue. Handing the queue to a new owner
      (``new_owner``) is MANAGE only.
    * delete and items/remove: MANAGE, or EDIT plus owning a CUSTOM queue.
    * items/add: EDIT on the experiment.
    * items/set-status: EDIT on the experiment and being an assigned user of the queue.
    * list: READ on the experiment. The response is narrowed in ``after_request`` for a
      caller without EDIT to the queues they are assigned to.

Owner and assigned users come from the queue as MLflow's tracking store returns it
(``created_by`` and ``users``). A queue that has no owner recorded is owned by nobody, and a
queue that cannot be resolved is not served.

A custom queue may not take a registered username as its name, on create or on rename: user
queues are named after their user, so such a name would stand in for that user's personal
queue. This is a data-integrity rule, so it applies to admins too.

A personal queue may be created for another user (the UI assigns work this way), but only
for an existing, active, non-service account. ``completed_by`` on an item records who did
the review, so it must be the caller.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from mlflow.exceptions import MlflowException
from mlflow.server.handlers import _get_tracking_store

from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.permissions import NO_PERMISSIONS, READ, Permission, intersect_permissions
from mlflow_oidc_auth.utils import all_source_values, effective_experiment_permission, get_experiment_ids, get_request_param_values
from mlflow_oidc_auth.validators._experiment_scope import names_only_caller, permission_on_all_experiments
from mlflow_oidc_auth.validators.experiment import validate_can_update_experiment

logger = get_logger()

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


def validate_can_manage_label_schema(username: str) -> bool:
    """MANAGE on the schema's experiment (update, delete); admin-only for a schema with none."""
    return _label_schema_permission(username, unscoped=NO_PERMISSIONS).can_manage


# ---------------------------------------------------------------------------
# Review queues: queue facts
# ---------------------------------------------------------------------------


def _normalize(name: object) -> str:
    """Trim and lowercase a user identifier, as MLflow stores assigned users."""
    return str(name or "").strip().lower()


def is_review_queue_member(queue, username: str) -> bool:
    """True if ``username`` is one of the queue's assigned users.

    Works on MLflow's ``ReviewQueue`` entity and on its protobuf message alike. MLflow
    stores assigned users trimmed and lowercased; they are normalized here as well, so a
    stored value in another case still compares equal. A queue without users has no
    members.

    Parameters:
        queue: The review queue (entity or protobuf message).
        username: The authenticated user.

    Returns:
        Whether the caller is assigned to the queue.
    """
    target = _normalize(username)
    return bool(target) and target in {_normalize(user) for user in (getattr(queue, "users", None) or [])}


def _is_review_queue_owner(queue, username: str) -> bool:
    """True if the queue's ``created_by`` is ``username`` (case-insensitive); never for an unowned queue."""
    owner = _normalize(getattr(queue, "created_by", None))
    return bool(owner) and owner == _normalize(username)


def _is_custom_queue(queue) -> bool:
    """True for a CUSTOM queue. ``queue_type`` is MLflow's ``ReviewQueueType`` (a str enum)."""
    from mlflow.genai.review_queues import ReviewQueueType

    return getattr(queue, "queue_type", None) == ReviewQueueType.CUSTOM


def _queue_permission(queue, username: str) -> Permission:
    return permission_on_all_experiments([getattr(queue, "experiment_id", None)], username)


def _requested_queues() -> list:
    """Every review queue the request names, in any source; MLflow's own ``queue_id`` first.

    A queue that cannot be resolved raises ``MlflowException`` (MLflow's not-found error),
    so the request is not served.
    """
    tracking_store = _get_tracking_store()
    return [tracking_store.get_review_queue(str(queue_id)) for queue_id in get_request_param_values("queue_id")]


def _all_queues(predicate: Callable[[object, Permission], bool], username: str) -> bool:
    """True only if ``predicate(queue, permission)`` holds for every queue the request names."""
    queues = _requested_queues()
    return bool(queues) and all(predicate(queue, _queue_permission(queue, username)) for queue in queues)


def _can_view(queue, permission: Permission, username: str) -> bool:
    if not permission.can_read:
        return False
    if permission.can_manage or is_review_queue_member(queue, username):
        return True
    return permission.can_update and _is_review_queue_owner(queue, username)


def _can_own_or_manage(queue, permission: Permission, username: str) -> bool:
    return permission.can_manage or (permission.can_update and _is_review_queue_owner(queue, username))


def _can_delete_or_prune(queue, permission: Permission, username: str) -> bool:
    # A USER queue's lifecycle belongs to a manager, never to its owner or assignee.
    return permission.can_manage or (permission.can_update and _is_review_queue_owner(queue, username) and _is_custom_queue(queue))


# ---------------------------------------------------------------------------
# Review queues: a custom queue's name may not be a registered username
# ---------------------------------------------------------------------------

# ReviewQueueType.USER, by proto name or number.
_USER_QUEUE_TYPE = {"USER", "1"}


def _registered_username_match(names: Iterable) -> Optional[str]:
    """The first registered username equal (case-insensitively) to any of ``names``, or None.

    Service accounts count as registered users. The match is case-insensitive because
    user queues are named after their user in lowercase.
    """
    from mlflow_oidc_auth.store import store

    targets = {_normalize(name) for name in names if isinstance(name, str) and name.strip()}
    if not targets:
        return None
    for username in [*store.list_usernames(is_service_account=False), *store.list_usernames(is_service_account=True)]:
        if _normalize(username) in targets:
            return username
    return None


def _reject_username_as_queue_name(names: Iterable, action: str) -> None:
    matched = _registered_username_match(names)
    if matched is not None:
        raise MlflowException.invalid_parameter_value(
            f"'{matched}' is a registered user. A custom review queue cannot {action} a username as its name; assign that user to a queue instead."
        )


def reject_create_review_queue_shadowing_user() -> None:
    """Refuse to create a custom review queue whose name is a registered username.

    Every ``name`` in any request source is checked unless every ``queue_type`` the
    request carries is USER (a user queue is named after its user by design).

    Raises:
        MlflowException: ``INVALID_PARAMETER_VALUE`` when a name is a registered username.
    """
    queue_types = {str(value).strip().upper() for value in all_source_values("queue_type")}
    if queue_types and queue_types <= _USER_QUEUE_TYPE:
        return
    _reject_username_as_queue_name(all_source_values("name"), "use")


def reject_rename_review_queue_shadowing_user() -> None:
    """Refuse to rename a custom review queue to a registered username.

    MLflow does not allow renaming a user queue at all, so only non-user queues are
    checked, and only when the request carries a ``name``.

    Raises:
        MlflowException: ``INVALID_PARAMETER_VALUE`` when the new name is a registered username.
    """
    from mlflow.genai.review_queues import ReviewQueueType

    names = all_source_values("name")
    if not names:
        return
    if all(getattr(queue, "queue_type", None) == ReviewQueueType.USER for queue in _requested_queues()):
        return
    _reject_username_as_queue_name(names, "be renamed to")


# ---------------------------------------------------------------------------
# Review queues: validators
# ---------------------------------------------------------------------------


def validate_can_create_review_queue(username: str) -> bool:
    """EDIT on the experiment; a custom queue's name may not be a registered username.

    A user queue (a personal queue created directly rather than through
    ``get-or-create-user``) must be named after an active, non-service account, as
    :func:`validate_can_get_or_create_user_queue` requires.
    """
    if not validate_can_update_experiment(username):
        return False
    queue_types = {str(value).strip().upper() for value in all_source_values("queue_type")}
    if queue_types & _USER_QUEUE_TYPE and not all(_is_assignable_user(name) for name in all_source_values("name")):
        return False
    reject_create_review_queue_shadowing_user()
    return True


def _is_assignable_user(name: str) -> bool:
    """True if ``name`` is an existing, active user account that is not a service account."""
    from mlflow_oidc_auth.store import store

    try:
        user = store.get_user_profile(str(name).strip())
    except MlflowException:
        return False
    return bool(user.active) and not user.is_service_account


def validate_can_get_or_create_user_queue(username: str) -> bool:
    """EDIT on the experiment; the queue's ``user`` must be an active, non-service account.

    MLflow's UI calls this with the ASSIGNEE as ``user`` when it routes a trace to a
    teammate, so the user need not be the caller. It must name a real person, though, so a
    queue cannot be created for an arbitrary string.
    """
    return all(_is_assignable_user(name) for name in all_source_values("user")) and validate_can_update_experiment(username)


def validate_can_view_review_queue(username: str) -> bool:
    """READ plus MANAGE, membership, or EDIT and ownership (get, items/list)."""
    return _all_queues(lambda queue, permission: _can_view(queue, permission, username), username)


def validate_can_view_review_queue_by_name(username: str) -> bool:
    """As :func:`validate_can_view_review_queue`, for a queue named within an experiment (get-by-name).

    A caller with MANAGE on the experiment is not checked further. Anyone else needs every
    named queue to exist and to be one they are assigned to or, with EDIT, own; a queue
    that cannot be found is refused.
    """
    experiment_ids = get_experiment_ids()
    permission = intersect_permissions(effective_experiment_permission(e, username).permission for e in experiment_ids)
    if not permission.can_read:
        return False
    if permission.can_manage:
        return True
    tracking_store = _get_tracking_store()
    for experiment_id in experiment_ids:
        for name in get_request_param_values("name"):
            try:
                queue = tracking_store.get_review_queue_by_name(str(experiment_id), name=str(name))
            except MlflowException:
                return False
            if not (is_review_queue_member(queue, username) or (permission.can_update and _is_review_queue_owner(queue, username))):
                return False
    return True


def validate_can_update_review_queue(username: str) -> bool:
    """MANAGE, or EDIT and ownership; MANAGE to hand the queue to a new owner.

    A custom queue may not be renamed to a registered username.
    """
    if all_source_values("new_owner"):
        allowed = _all_queues(lambda _queue, permission: permission.can_manage, username)
    else:
        allowed = _all_queues(lambda queue, permission: _can_own_or_manage(queue, permission, username), username)
    if allowed:
        reject_rename_review_queue_shadowing_user()
    return allowed


def validate_can_delete_review_queue(username: str) -> bool:
    """MANAGE, or EDIT and ownership of a CUSTOM queue."""
    return _all_queues(lambda queue, permission: _can_delete_or_prune(queue, permission, username), username)


def validate_can_add_items_to_review_queue(username: str) -> bool:
    """EDIT on the queue's experiment (items/add)."""
    return _all_queues(lambda _queue, permission: permission.can_update, username)


def validate_can_remove_items_from_review_queue(username: str) -> bool:
    """MANAGE, or EDIT and ownership of a CUSTOM queue (items/remove)."""
    return _all_queues(lambda queue, permission: _can_delete_or_prune(queue, permission, username), username)


# ReviewStatus.PENDING, by name or by proto number.
_PENDING_STATUS = {"PENDING", "1"}


def validate_can_set_review_queue_item_status(username: str) -> bool:
    """EDIT on the queue's experiment and being assigned to the queue.

    Even a manager must be assigned to a queue to review through it. ``completed_by`` must
    be the caller, and is required when the item moves to a terminal state.
    """
    if not names_only_caller("completed_by", username):
        return False
    # Moving an item to a terminal state (COMPLETE / DECLINED) records who reviewed it, so
    # the caller must be named; MLflow's UI and client always send it there.
    statuses = {str(s).strip().upper() for s in all_source_values("status")}
    if statuses - _PENDING_STATUS and not all_source_values("completed_by"):
        return False
    return _all_queues(lambda queue, permission: permission.can_update and is_review_queue_member(queue, username), username)


def enforce_review_queue_name_not_username(validator: Optional[Callable[[str], bool]]) -> None:
    """Apply the queue-name rule for a caller who skips validators (an admin).

    Non-admins meet the rule inside :func:`validate_can_create_review_queue` and
    :func:`validate_can_update_review_queue`, after their permission is confirmed. A no-op
    for every other route.

    Parameters:
        validator: The validator the request was routed to, or None.

    Raises:
        MlflowException: ``INVALID_PARAMETER_VALUE`` when the name is a registered username.
    """
    if validator is validate_can_create_review_queue:
        reject_create_review_queue_shadowing_user()
    elif validator is validate_can_update_review_queue:
        reject_rename_review_queue_shadowing_user()
