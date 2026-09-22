"""Error handling in the access-token endpoint (issue #338, raised in review of #339).

Two paths returned an opaque 500 for conditions that have a correct status code:

* an ISO 8601 expiration written without a UTC offset, because comparing a naive datetime to an
  aware one raises ``TypeError`` and the handler only caught ``ValueError``;
* a target username that does not exist, because ``get_user_profile`` raises rather than
  returning ``None``, so the 404 branch was unreachable.

The first mattered beyond tidiness: an operator who hits an unexplained 500 naturally retries
with the ``expiration`` field dropped, and since #338 that issues a token which never expires.
A wrong status code turned into an accidental permanent credential.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.models import CreateAccessTokenRequest
from mlflow_oidc_auth.routers.users import create_access_token


def _store(expiration=None):
    store = MagicMock()
    user = MagicMock()
    user.password_expiration = expiration
    store.get_user_profile.return_value = user
    return store


async def _rotate(store, expiration_str=None, username=None, is_admin=True):
    request = None
    if expiration_str is not None or username is not None:
        request = CreateAccessTokenRequest(expiration=expiration_str, username=username)
    with patch("mlflow_oidc_auth.routers.users.store", store):
        return await create_access_token(
            token_request=request,
            current_username="admin@example.com",
            is_admin=is_admin,
        )


class TestNaiveExpirationIsAccepted:
    """A missing UTC offset is read as UTC, not turned into a 500."""

    @staticmethod
    def _soon(**kwargs) -> datetime:
        """A UTC instant inside the endpoint's 1-year cap."""
        return datetime.now(timezone.utc) + timedelta(days=30, **kwargs)

    @pytest.mark.parametrize("date_only", [False, True])
    @pytest.mark.asyncio
    async def test_offsetless_expiration_is_accepted(self, date_only):
        """Previously TypeError -> outer handler -> 500 Failed to create access token.

        Covers both ISO 8601 forms that carry no offset: a full timestamp and a bare date.
        """
        store = _store()
        naive = self._soon().replace(tzinfo=None)
        expiration_str = naive.date().isoformat() if date_only else naive.isoformat()

        result = await _rotate(store, expiration_str=expiration_str)

        assert result.status_code == 200
        stored = store.create_user_token.call_args.kwargs["expires_at"]
        assert stored is not None
        assert stored.tzinfo is not None, "expiration must be normalized to an aware datetime"

    @pytest.mark.asyncio
    async def test_offsetless_expiration_is_interpreted_as_utc(self):
        store = _store()
        naive = self._soon().replace(microsecond=0, tzinfo=None)

        await _rotate(store, expiration_str=naive.isoformat())

        stored = store.create_user_token.call_args.kwargs["expires_at"]
        assert stored == naive.replace(tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_an_offset_is_still_respected(self):
        """Normalizing the naive case must not trample an explicit offset."""
        store = _store()
        aware = self._soon().astimezone(timezone(timedelta(hours=5))).replace(microsecond=0)

        await _rotate(store, expiration_str=aware.isoformat())

        stored = store.create_user_token.call_args.kwargs["expires_at"]
        assert stored.utcoffset() == timedelta(hours=5)
        assert stored == aware

    @pytest.mark.asyncio
    async def test_a_past_offsetless_expiration_is_still_rejected(self):
        """The negative case: accepting the format must not stop validating the value."""
        store = _store()
        past = (datetime.now(timezone.utc) - timedelta(days=2)).replace(tzinfo=None).isoformat()

        with pytest.raises(HTTPException) as exc:
            await _rotate(store, expiration_str=past)

        assert exc.value.status_code == 400
        assert "must be in the future" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_a_far_future_offsetless_expiration_is_still_rejected(self):
        store = _store()
        far = (datetime.now(timezone.utc) + timedelta(days=800)).replace(tzinfo=None).isoformat()

        with pytest.raises(HTTPException) as exc:
            await _rotate(store, expiration_str=far)

        assert exc.value.status_code == 400
        assert "less than 1 year" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_genuinely_malformed_input_is_still_a_400(self):
        store = _store()

        with pytest.raises(HTTPException) as exc:
            await _rotate(store, expiration_str="not-a-date")

        assert exc.value.status_code == 400
        assert "Invalid expiration date format" in str(exc.value.detail)


class TestUnknownUserIsNotFound:
    """A missing target user is a 404, not a 500."""

    @pytest.mark.asyncio
    async def test_unknown_target_username_returns_404(self):
        store = MagicMock()
        store.get_user_profile.side_effect = MlflowException("User 'ghost@example.com' not found")

        with pytest.raises(HTTPException) as exc:
            await _rotate(store, username="ghost@example.com")

        assert exc.value.status_code == 404
        assert "ghost@example.com" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_no_token_is_issued_for_an_unknown_user(self):
        """The 404 must short-circuit before anything is written."""
        store = MagicMock()
        store.get_user_profile.side_effect = MlflowException("not found")

        with pytest.raises(HTTPException):
            await _rotate(store, username="ghost@example.com")

        store.update_user.assert_not_called()
