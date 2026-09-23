"""Resources a departing user leaves without a manager (issue #324).

When a directory deactivates or deletes someone, anything *only they* could manage becomes
unmanageable by anyone short of an administrator. That is not a reason to block the
deprovisioning — access removal must never wait on housekeeping — but it is something an
operator needs to hear about. This module finds those resources and reports them as
``resource.orphaned`` audit events, and, when ``ORPHAN_FALLBACK_PRINCIPAL`` is configured, hands
them to that principal as part of the hard delete that cascades the departing user's grants away.

Not to be confused with :mod:`mlflow_oidc_auth.ownership`, which is the ``managed_by`` write guard
on user rows.

**What counts as another holder.** A resource is orphaned when the user holds ``MANAGE`` on it
directly and nobody else would still be able to manage it:

* no *other active* user holds ``MANAGE`` directly, and
* no group holding ``MANAGE`` on it has an active member other than the departing user.

Regex grants are not resolved against resource names: doing so needs the tracking store, and a
pattern grant is by nature not "the last holder" of any one resource. Admins are not counted as
holders either — an admin can always recover a resource, which is precisely why an orphan is a
report and never a refusal.
"""

from typing import Dict, List, Optional, Tuple

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

MANAGE = "MANAGE"

#: ``resource_type`` values used in ``resource.orphaned`` events.
EXPERIMENT = "experiment"
REGISTERED_MODEL = "registered_model"  # prompts are registered models and share these grants
SCORER = "scorer"
GATEWAY_ENDPOINT = "gateway_endpoint"
GATEWAY_MODEL_DEFINITION = "gateway_model_definition"
WORKSPACE = "workspace"


def _specs():
    """``(resource_type, user_model, group_model, key_columns)`` for each resource kind."""
    from mlflow_oidc_auth.db.models import (
        SqlExperimentGroupPermission,
        SqlExperimentPermission,
        SqlGatewayEndpointGroupPermission,
        SqlGatewayEndpointPermission,
        SqlGatewayModelDefinitionGroupPermission,
        SqlGatewayModelDefinitionPermission,
        SqlGatewaySecretGroupPermission,
        SqlGatewaySecretPermission,
        SqlRegisteredModelGroupPermission,
        SqlRegisteredModelPermission,
        SqlScorerGroupPermission,
        SqlScorerPermission,
        SqlWorkspaceGroupPermission,
        SqlWorkspacePermission,
    )

    return [
        (EXPERIMENT, SqlExperimentPermission, SqlExperimentGroupPermission, ("experiment_id",)),
        (REGISTERED_MODEL, SqlRegisteredModelPermission, SqlRegisteredModelGroupPermission, ("name",)),
        (SCORER, SqlScorerPermission, SqlScorerGroupPermission, ("experiment_id", "scorer_name")),
        (GATEWAY_ENDPOINT, SqlGatewayEndpointPermission, SqlGatewayEndpointGroupPermission, ("endpoint_id",)),
        (GATEWAY_MODEL_DEFINITION, SqlGatewayModelDefinitionPermission, SqlGatewayModelDefinitionGroupPermission, ("model_definition_id",)),
        # The resource-type label is written inline: a module constant carrying "secret" in its
        # name makes static analysis treat the label (not a secret) as sensitive wherever it is logged.
        ("gateway_secret", SqlGatewaySecretPermission, SqlGatewaySecretGroupPermission, ("secret_id",)),
        (WORKSPACE, SqlWorkspacePermission, SqlWorkspaceGroupPermission, ("workspace",)),
    ]


def _resource_id(keys: Tuple[str, ...]) -> str:
    return "/".join(str(k) for k in keys)


def _key_columns(model, names):
    return [getattr(model, n) for n in names if hasattr(model, n)]


def _find_in_session(session, user_id: int) -> List[Tuple[str, str]]:
    """Orphan detection against an open session. See :func:`find_orphaned_resources`."""
    from mlflow_oidc_auth.db.models import SqlUser, SqlUserGroup

    orphans: List[Tuple[str, str]] = []
    # Groups with at least one active member who is not the departing user.
    managed_groups = {
        row[0]
        for row in session.query(SqlUserGroup.group_id)
        .join(SqlUser, SqlUser.id == SqlUserGroup.user_id)
        .filter(SqlUser.active.is_(True), SqlUser.id != user_id)
        .distinct()
        .all()
    }

    for resource_type, user_model, group_model, key_names in _specs():
        user_keys = _key_columns(user_model, key_names)
        group_keys = _key_columns(group_model, key_names)
        if len(user_keys) != len(key_names) or len(group_keys) != len(key_names):
            logger.warning("Skipping orphan check for %s: unexpected permission schema", resource_type)
            continue

        mine = {tuple(r) for r in session.query(*user_keys).filter(user_model.user_id == user_id, user_model.permission == MANAGE).all()}
        if not mine:
            continue

        others = {
            tuple(r)
            for r in session.query(*user_keys)
            .join(SqlUser, SqlUser.id == user_model.user_id)
            .filter(user_model.permission == MANAGE, user_model.user_id != user_id, SqlUser.active.is_(True))
            .all()
        }
        groups = {
            tuple(r[:-1]) for r in session.query(*group_keys, group_model.group_id).filter(group_model.permission == MANAGE).all() if r[-1] in managed_groups
        }
        for keys in sorted(mine - others - groups):
            orphans.append((resource_type, _resource_id(keys)))
    return orphans


def _store_or_singleton(store):
    if store is None:
        from mlflow_oidc_auth.store import store as store_singleton

        return store_singleton
    return store


def find_orphaned_resources(username: str, store=None) -> List[Tuple[str, str]]:
    """Resources for which ``username`` is the last holder of ``MANAGE``.

    Parameters:
        username: The departing user.
        store: The store to read; defaults to the singleton.

    Returns:
        ``[(resource_type, resource_id), ...]``. A scorer's id is ``<experiment_id>/<scorer_name>``.
        Empty for an unknown user.
    """
    from mlflow_oidc_auth.db.models import SqlUser
    from mlflow_oidc_auth.repository.user import normalize_username

    store = _store_or_singleton(store)
    with store.ManagedSessionMaker() as session:
        user = session.query(SqlUser.id).filter(SqlUser.username == normalize_username(username)).one_or_none()
        if user is None:
            return []
        return _find_in_session(session, user[0])


def _valid_fallback(session, fallback: Optional[str], departing_id: int):
    """The fallback principal's row, or None when it may not receive a hand-over.

    It must exist, be active, not be a service account and not be the departing user. A service
    account is refused because it is a credential, not a person accountable for the resource.
    """
    from mlflow_oidc_auth.db.models import SqlUser
    from mlflow_oidc_auth.repository.user import normalize_username

    if not fallback:
        return None
    target = session.query(SqlUser).filter(SqlUser.username == normalize_username(fallback)).one_or_none()
    if target is None or not target.active or target.is_service_account or target.id == departing_id:
        logger.warning(
            "ORPHAN_FALLBACK_PRINCIPAL %r is not an existing, active, non-service-account user other than the one being deleted; "
            "orphaned resources are reported only",
            fallback,
        )
        return None
    return target


def _transfer_in_session(session, target_id: int, orphans: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Grant ``MANAGE`` on each orphan to ``target_id``, raising an existing lower grant."""
    specs: Dict[str, tuple] = {spec[0]: spec for spec in _specs()}
    transferred: List[Tuple[str, str]] = []
    for resource_type, resource_id in orphans:
        _, user_model, _, key_names = specs[resource_type]
        values = resource_id.split("/", len(key_names) - 1)
        criteria = {name: value for name, value in zip(key_names, values)}
        existing = session.query(user_model).filter_by(user_id=target_id, **criteria).one_or_none()
        if existing is None:
            session.add(user_model(user_id=target_id, permission=MANAGE, **criteria))
        else:
            existing.permission = MANAGE
        transferred.append((resource_type, resource_id))
    session.flush()
    return transferred


def _audit(orphans, transferred, fallback, *, actor: str, source: str, username: str) -> None:
    from mlflow_oidc_auth.audit import emit_audit_event

    for resource_type, resource_id in orphans:
        try:
            detail = {"user": username, "source": source}
            if (resource_type, resource_id) in transferred:
                detail["transferred_to"] = fallback
            emit_audit_event("resource.orphaned", actor=actor, resource_type=resource_type, resource_id=resource_id, detail=detail)
        except Exception:
            logger.exception("Could not audit orphaned %s %s", resource_type, resource_id)


def report_orphans(username: str, *, actor: str, source: str, store=None) -> List[Tuple[str, str]]:
    """Find and audit the resources ``username`` leaves unmanaged. For deactivation.

    Nothing is handed over: a deactivated user may come back, and their grants are still theirs.

    **Never raises.** Deprovisioning is the security-relevant half of this operation and must not
    wait on, or be undone by, a failure in the housekeeping half.

    Returns:
        The orphans found; empty on failure.
    """
    try:
        orphans = find_orphaned_resources(username, store=store)
    except Exception:
        logger.exception("Orphan detection failed for %s; continuing without it", username)
        return []
    _audit(orphans, set(), None, actor=actor, source=source, username=username)
    return orphans


def delete_user_reporting_orphans(username: str, *, actor: str, source: str, store=None) -> List[Tuple[str, str]]:
    """Hard-delete ``username``, handing orphaned resources to ``ORPHAN_FALLBACK_PRINCIPAL``.

    Detection and hand-over run inside the delete's own transaction: detection before the cascade
    removes the grants it reads, the hand-over only after the cascade and the user row's delete
    have been flushed (the fallback's grants are independent of the rows removed). So a delete
    that fails (the last-admin invariant, a database error in the cascade) never reaches the
    hand-over, and a failed commit rolls it back — a hand-over can never outlive a refused delete.
    This ordering, not savepoint semantics, is what guarantees it: on SQLite a savepoint opened
    before any write begins the transaction itself and its release commits it.

    Neither half raises: a failure is logged and the delete proceeds without it. The hand-over
    runs under a savepoint — by then nested inside a transaction the cascade has begun — so a
    failed hand-over is undone without undoing the delete. Events are emitted only after the
    delete has committed.

    Returns:
        The orphans found.

    Raises:
        MlflowException: Whatever the delete itself raises.
    """
    store = _store_or_singleton(store)
    try:
        from mlflow_oidc_auth.config import config

        fallback = getattr(config, "ORPHAN_FALLBACK_PRINCIPAL", None) or None
    except Exception:
        fallback = None

    found: List[Tuple[str, str]] = []
    transferred: List[Tuple[str, str]] = []
    departing: List[int] = []

    def before_cascade(session, user) -> None:
        try:
            with session.begin_nested():
                found.extend(_find_in_session(session, user.id))
            departing.append(user.id)
        except Exception:
            logger.exception("Orphan detection failed while deleting %s; deleting without it", username)
            found.clear()

    def after_cascade(session) -> None:
        if not found or not departing:
            return
        try:
            with session.begin_nested():
                target = _valid_fallback(session, fallback, departing[0])
                if target is not None:
                    transferred.extend(_transfer_in_session(session, target.id, found))
        except Exception:
            logger.exception("Orphan hand-over failed while deleting %s; deleting without it", username)
            transferred.clear()

    store.delete_user_with_hook(username, before_cascade, after_cascade)

    if transferred:
        try:
            from mlflow_oidc_auth.utils.permissions import flush_permission_cache

            flush_permission_cache()
        except Exception:
            logger.warning("Permission cache flush failed after orphan hand-over; entries expire via TTL")
    _audit(found, set(transferred), fallback, actor=actor, source=source, username=username)
    return found
