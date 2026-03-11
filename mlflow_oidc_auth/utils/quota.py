from datetime import datetime, timedelta, timezone
from typing import Optional

from mlflow.exceptions import MlflowException
from mlflow.protos.databricks_pb2 import RESOURCE_LIMIT_EXCEEDED

from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.logger import get_logger
from mlflow_oidc_auth.store import store

logger = get_logger()


def get_experiment_owner(experiment_id: str) -> Optional[str]:
    """Return the username of the OWNER of an experiment, or None."""
    from mlflow_oidc_auth.permissions import OWNER

    try:
        perms = store.list_experiment_permissions_for_experiment(experiment_id)
        for perm in perms:
            if perm.permission == OWNER.name:
                user = store.get_user_by_id(perm.user_id)
                if user:
                    return user.username
    except Exception:
        pass
    return None


def enforce_quota(username: str) -> None:
    """Raise MlflowException if the user's storage quota is exceeded.

    This is a no-op when:
    - No quota row exists for the user
    - The global default quota is unlimited (None)
    - The user's quota_bytes is None
    """
    quota = store.get_user_quota(username)

    # Determine effective quota_bytes
    if quota is not None:
        effective_quota = quota.quota_bytes
    else:
        effective_quota = config.QUOTA_DEFAULT_BYTES

    if effective_quota is None:
        return  # Unlimited

    used = quota.used_bytes if quota is not None else 0

    if used >= effective_quota:
        raise MlflowException(
            f"Storage quota exceeded for user '{username}'. "
            f"Used {used} bytes of {effective_quota} bytes.",
            RESOURCE_LIMIT_EXCEEDED,
        )


def reconcile_user_quota(username: str) -> None:
    """Recalculate used_bytes for a single user and apply threshold logic."""
    quota = store.get_user_quota(username)
    if quota is None:
        return

    effective_quota = quota.quota_bytes if quota.quota_bytes is not None else config.QUOTA_DEFAULT_BYTES
    if effective_quota is None:
        return  # No quota to reconcile

    used = _calculate_used_bytes(username)
    store.update_user_quota_used_bytes(username, used)

    # Threshold checks
    pct = used / effective_quota
    soft_fraction = quota.soft_cap_fraction

    now = datetime.now(timezone.utc)

    from mlflow_oidc_auth.utils.email import send_hard_cap_notification, send_soft_cap_warning

    # Soft cap notification
    email_address = getattr(quota, "email", None)

    if pct >= soft_fraction:
        last_notified = quota.soft_notified_at
        should_notify = last_notified is None or (now - last_notified) > timedelta(hours=24)
        if should_notify:
            # Only stamp soft_notified_at if the email was actually sent.
            # If email_address is absent, leave it NULL so the reconciler retries
            # as soon as the user signs in and their email is recorded.
            sent = send_soft_cap_warning(username, used, effective_quota, pct, email_address)
            if sent:
                store.set_quota_soft_notified_at(username, now)
    else:
        if quota.soft_notified_at is not None:
            store.set_quota_soft_notified_at(username, None)

    # Hard cap
    if used >= effective_quota:
        if not quota.hard_blocked:
            store.set_quota_hard_blocked(username, True)
            send_hard_cap_notification(username, used, effective_quota, email_address)
    else:
        if quota.hard_blocked:
            store.set_quota_hard_blocked(username, False)


def _calculate_used_bytes(username: str) -> int:
    """Sum artifact sizes across all experiments owned by the given user."""
    import mlflow
    from mlflow_oidc_auth.permissions import OWNER

    client = mlflow.tracking.MlflowClient()
    total = 0

    try:
        # Get all experiment_ids owned by this user
        user_perms = store.list_experiment_permissions(username)
        owned_experiment_ids = [p.experiment_id for p in user_perms if p.permission == OWNER.name]

        for exp_id in owned_experiment_ids:
            try:
                runs = client.search_runs(experiment_ids=[exp_id])
                for run in runs:
                    total += _sum_artifacts(client, run.info.run_id, "")
            except Exception as e:
                logger.warning(f"Error calculating artifacts for experiment {exp_id}: {e}")

    except Exception as e:
        logger.warning(f"Error calculating used bytes for user {username}: {e}")

    return total


def _sum_artifacts(client, run_id: str, path: str) -> int:
    """Recursively sum artifact file sizes for a run."""
    total = 0
    try:
        artifacts = client.list_artifacts(run_id, path)
        for artifact in artifacts:
            if artifact.is_dir:
                total += _sum_artifacts(client, run_id, artifact.path)
            elif artifact.file_size is not None:
                total += artifact.file_size
    except Exception:
        pass
    return total


def reconcile_all_quotas() -> None:
    """Reconcile quotas for all users that have a quota row."""
    try:
        quotas = store.list_all_user_quotas()
        for quota in quotas:
            try:
                user = store.get_user_by_id(quota.user_id)
                if user:
                    reconcile_user_quota(user.username)
            except Exception as e:
                logger.warning(f"Error reconciling quota for user_id {quota.user_id}: {e}")
    except Exception as e:
        logger.error(f"Error during quota reconciliation: {e}")


def cleanup_trash(retention_days: int) -> None:
    """Permanently delete soft-deleted experiments older than retention_days."""
    import time
    import mlflow

    client = mlflow.tracking.MlflowClient()
    cutoff_ms = (time.time() - retention_days * 86400) * 1000  # MLflow uses milliseconds

    try:
        deleted_experiments = client.search_experiments(
            view_type=mlflow.entities.ViewType.DELETED_ONLY,
        )
        affected_owners = set()
        for exp in deleted_experiments:
            deletion_time = getattr(exp, "last_update_time", None) or getattr(exp, "creation_time", 0)
            if deletion_time and deletion_time < cutoff_ms:
                owner = get_experiment_owner(exp.experiment_id)
                try:
                    # Hard-delete via underlying store
                    from mlflow.server.handlers import _get_tracking_store
                    _get_tracking_store().delete_experiment(exp.experiment_id)
                    logger.info(f"Permanently deleted experiment {exp.experiment_id} (owner: {owner})")
                    if owner:
                        affected_owners.add(owner)
                except Exception as e:
                    logger.warning(f"Could not hard-delete experiment {exp.experiment_id}: {e}")

        for owner in affected_owners:
            try:
                reconcile_user_quota(owner)
            except Exception as e:
                logger.warning(f"Error reconciling quota for {owner} after trash cleanup: {e}")

    except Exception as e:
        logger.error(f"Error during trash cleanup: {e}")
