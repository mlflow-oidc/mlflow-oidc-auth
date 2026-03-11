"""Unit tests for the storage quota system."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_quota(quota_bytes=None, used_bytes=0, soft_cap_fraction=0.9, hard_blocked=False, soft_notified_at=None):
    q = MagicMock()
    q.quota_bytes = quota_bytes
    q.used_bytes = used_bytes
    q.soft_cap_fraction = soft_cap_fraction
    q.hard_blocked = hard_blocked
    q.soft_notified_at = soft_notified_at
    return q


# ---------------------------------------------------------------------------
# enforce_quota
# ---------------------------------------------------------------------------


class TestEnforceQuota:
    def test_no_quota_row_no_global_default_allows(self):
        """When there is no quota row and no global default, request should pass."""
        with patch("mlflow_oidc_auth.utils.quota.store") as mock_store, patch("mlflow_oidc_auth.utils.quota.config") as mock_config:
            mock_store.get_user_quota.return_value = None
            mock_config.QUOTA_DEFAULT_BYTES = None

            from mlflow_oidc_auth.utils.quota import enforce_quota

            enforce_quota("alice")  # Should not raise

    def test_no_quota_row_with_global_default_unlimited(self):
        """Global default of None means unlimited."""
        with patch("mlflow_oidc_auth.utils.quota.store") as mock_store, patch("mlflow_oidc_auth.utils.quota.config") as mock_config:
            mock_store.get_user_quota.return_value = None
            mock_config.QUOTA_DEFAULT_BYTES = None

            from mlflow_oidc_auth.utils.quota import enforce_quota

            enforce_quota("bob")  # Should not raise

    def test_within_quota_allows(self):
        """Request within quota should pass."""
        with patch("mlflow_oidc_auth.utils.quota.store") as mock_store, patch("mlflow_oidc_auth.utils.quota.config") as mock_config:
            mock_store.get_user_quota.return_value = _make_quota(quota_bytes=1_000_000, used_bytes=500_000)
            mock_config.QUOTA_DEFAULT_BYTES = None

            from mlflow_oidc_auth.utils.quota import enforce_quota

            enforce_quota("alice")  # Should not raise

    def test_exactly_at_quota_raises(self):
        """Request at exactly quota_bytes should be blocked."""
        from mlflow.exceptions import MlflowException

        with patch("mlflow_oidc_auth.utils.quota.store") as mock_store, patch("mlflow_oidc_auth.utils.quota.config") as mock_config:
            mock_store.get_user_quota.return_value = _make_quota(quota_bytes=1_000_000, used_bytes=1_000_000)
            mock_config.QUOTA_DEFAULT_BYTES = None

            from mlflow_oidc_auth.utils.quota import enforce_quota

            with pytest.raises(MlflowException, match="quota exceeded|Storage quota"):
                enforce_quota("alice")

    def test_over_quota_raises(self):
        """Request over quota should be blocked."""
        from mlflow.exceptions import MlflowException

        with patch("mlflow_oidc_auth.utils.quota.store") as mock_store, patch("mlflow_oidc_auth.utils.quota.config") as mock_config:
            mock_store.get_user_quota.return_value = _make_quota(quota_bytes=1_000_000, used_bytes=2_000_000)
            mock_config.QUOTA_DEFAULT_BYTES = None

            from mlflow_oidc_auth.utils.quota import enforce_quota

            with pytest.raises(MlflowException):
                enforce_quota("alice")

    def test_null_quota_bytes_allows(self):
        """quota_bytes = None on the row means unlimited."""
        with patch("mlflow_oidc_auth.utils.quota.store") as mock_store, patch("mlflow_oidc_auth.utils.quota.config") as mock_config:
            mock_store.get_user_quota.return_value = _make_quota(quota_bytes=None, used_bytes=999_999_999)
            mock_config.QUOTA_DEFAULT_BYTES = None

            from mlflow_oidc_auth.utils.quota import enforce_quota

            enforce_quota("alice")  # Should not raise


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


class TestReconcileUserQuota:
    def _make_store(self, username, quota, owner_experiment_ids=None):
        mock_store = MagicMock()
        mock_store.get_user_quota.return_value = quota
        if owner_experiment_ids is not None:
            perm_mocks = []
            for exp_id in owner_experiment_ids:
                p = MagicMock()
                p.experiment_id = exp_id
                p.permission = "OWNER"
                perm_mocks.append(p)
            mock_store.list_experiment_permissions.return_value = perm_mocks
        return mock_store

    def test_no_quota_row_is_noop(self):
        """reconcile_user_quota should be a no-op when there is no quota row."""
        with patch("mlflow_oidc_auth.utils.quota.store") as mock_store, patch("mlflow_oidc_auth.utils.quota.config") as mock_config:
            mock_store.get_user_quota.return_value = None
            mock_config.QUOTA_DEFAULT_BYTES = None

            from mlflow_oidc_auth.utils.quota import reconcile_user_quota

            reconcile_user_quota("alice")
            mock_store.update_user_quota_used_bytes.assert_not_called()

    def test_reconcile_aggregates_artifact_sizes(self):
        """Reconciliation should sum artifact sizes and update used_bytes."""
        quota = _make_quota(quota_bytes=100_000_000, used_bytes=0)

        with (
            patch("mlflow_oidc_auth.utils.quota.store") as mock_store,
            patch("mlflow_oidc_auth.utils.quota.config") as mock_config,
            patch("mlflow_oidc_auth.utils.quota._calculate_used_bytes", return_value=5_000_000) as mock_calc,
            patch("mlflow_oidc_auth.utils.email.send_soft_cap_warning") as mock_email,
        ):
            mock_store.get_user_quota.return_value = quota
            mock_config.QUOTA_DEFAULT_BYTES = None

            from mlflow_oidc_auth.utils.quota import reconcile_user_quota

            reconcile_user_quota("alice")

            mock_calc.assert_called_once_with("alice")
            mock_store.update_user_quota_used_bytes.assert_called_once_with("alice", 5_000_000)
            mock_email.assert_not_called()

    def test_reconcile_sends_soft_cap_email(self):
        """Reconciliation should send a warning when soft cap is crossed."""
        quota = _make_quota(quota_bytes=10_000_000, used_bytes=0, soft_cap_fraction=0.9, soft_notified_at=None)

        with (
            patch("mlflow_oidc_auth.utils.quota.store") as mock_store,
            patch("mlflow_oidc_auth.utils.quota.config") as mock_config,
            patch("mlflow_oidc_auth.utils.quota._calculate_used_bytes", return_value=9_500_000),
            patch("mlflow_oidc_auth.utils.email.send_soft_cap_warning") as mock_email,
        ):
            mock_store.get_user_quota.return_value = quota
            mock_config.QUOTA_DEFAULT_BYTES = None

            from mlflow_oidc_auth.utils.quota import reconcile_user_quota

            reconcile_user_quota("alice")
            mock_email.assert_called_once()


# ---------------------------------------------------------------------------
# Ownership transfer
# ---------------------------------------------------------------------------


class TestOwnershipTransfer:
    def test_get_experiment_owner_returns_owner(self):
        """get_experiment_owner should return the username of the OWNER."""
        perm = MagicMock()
        perm.permission = "OWNER"
        perm.user_id = 42

        user = MagicMock()
        user.username = "alice"

        with patch("mlflow_oidc_auth.utils.quota.store") as mock_store:
            mock_store.list_experiment_permissions_for_experiment.return_value = [perm]
            mock_store.get_user_by_id.return_value = user

            from mlflow_oidc_auth.utils.quota import get_experiment_owner

            assert get_experiment_owner("exp-123") == "alice"

    def test_get_experiment_owner_returns_none_when_no_owner(self):
        """get_experiment_owner should return None when no OWNER row exists."""
        perm = MagicMock()
        perm.permission = "MANAGE"
        perm.user_id = 42

        with patch("mlflow_oidc_auth.utils.quota.store") as mock_store:
            mock_store.list_experiment_permissions_for_experiment.return_value = [perm]

            from mlflow_oidc_auth.utils.quota import get_experiment_owner

            assert get_experiment_owner("exp-123") is None


# ---------------------------------------------------------------------------
# OWNER permission constant
# ---------------------------------------------------------------------------


class TestOwnerPermission:
    def test_owner_in_all_permissions(self):
        from mlflow_oidc_auth.permissions import ALL_PERMISSIONS, OWNER

        assert "OWNER" in ALL_PERMISSIONS
        assert ALL_PERMISSIONS["OWNER"] is OWNER

    def test_owner_has_manage_capability(self):
        from mlflow_oidc_auth.permissions import OWNER

        assert OWNER.can_manage is True
        assert OWNER.can_delete is True
        assert OWNER.can_update is True
        assert OWNER.can_use is True
        assert OWNER.can_read is True

    def test_owner_priority_higher_than_manage(self):
        from mlflow_oidc_auth.permissions import MANAGE, OWNER

        assert OWNER.priority > MANAGE.priority
