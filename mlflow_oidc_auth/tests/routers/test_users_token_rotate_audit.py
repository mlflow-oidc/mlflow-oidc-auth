"""Audit detail emitted when an access token is rotated (issue #338).

Rotating without an ``expiration`` replaces an expiring token with one that does not expire.
That widens the credential's lifetime, so it is recorded rather than left silent — these tests
pin that the signal is actually emitted and is not a constant.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.models import CreateAccessTokenRequest
from mlflow_oidc_auth.routers.users import create_access_token


def _store_with_expiration(expiration):
    """A mock store whose current user carries ``expiration``."""
    store = MagicMock()
    user = MagicMock()
    user.password_expiration = expiration
    store.get_user_profile.return_value = user
    return store


async def _rotate(store, token_request=None):
    """Drive the endpoint and return the audit call's kwargs."""
    with patch("mlflow_oidc_auth.routers.users.store", store):
        with patch("mlflow_oidc_auth.routers.users.emit_audit_event") as audit:
            result = await create_access_token(
                token_request=token_request,
                current_username="user@example.com",
                is_admin=False,
            )
    assert result.status_code == 200
    audit.assert_called_once()
    return audit.call_args


class TestTokenRotateAudit:
    @pytest.mark.asyncio
    async def test_dropping_an_expiry_is_recorded(self):
        """Expiring token, rotated with no expiration: the widening must be visible."""
        store = _store_with_expiration(datetime.now(timezone.utc) + timedelta(days=30))

        call = await _rotate(store)

        assert call[0][0] == "user.token_rotate"
        assert call[1]["detail"]["expiration_cleared"] is True
        assert call[1]["detail"]["expiration"] is None

    @pytest.mark.asyncio
    async def test_rotating_a_non_expiring_token_is_not_recorded_as_a_widening(self):
        """Nothing was dropped, so the flag must be False — otherwise it is noise, not a signal."""
        store = _store_with_expiration(None)

        call = await _rotate(store)

        assert call[1]["detail"]["expiration_cleared"] is False

    @pytest.mark.asyncio
    async def test_rotating_with_an_expiration_is_not_a_widening(self):
        """A replacement expiry is not a drop, and the new value is recorded."""
        store = _store_with_expiration(datetime.now(timezone.utc) + timedelta(days=1))
        wanted = datetime.now(timezone.utc) + timedelta(days=30)

        call = await _rotate(store, CreateAccessTokenRequest(expiration=wanted.isoformat()))

        assert call[1]["detail"]["expiration_cleared"] is False
        assert call[1]["detail"]["expiration"] is not None

    @pytest.mark.asyncio
    async def test_the_new_expiration_is_passed_to_the_store(self):
        """Guards the router half of the fix: what is audited is what is stored."""
        store = _store_with_expiration(datetime.now(timezone.utc) - timedelta(days=1))

        await _rotate(store)

        assert store.update_user.call_args[1]["password_expiration"] is None
