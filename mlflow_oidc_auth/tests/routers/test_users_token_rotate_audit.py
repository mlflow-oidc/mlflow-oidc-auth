"""Audit detail emitted when an access token is rotated (issues #338, #189).

Tokens always expire since #189: rotating without an ``expiration`` issues one that expires in a
year. The audit event records the expiry that was issued, whether it was the default, and
whether a previous ``default`` token was replaced — what an operator needs to reconstruct who
held which credential when.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.models import CreateAccessTokenRequest
from mlflow_oidc_auth.repository.user_token import UserTokenRecord
from mlflow_oidc_auth.routers.users import create_access_token


def _store(replaced=True):
    store = MagicMock()
    user = MagicMock()
    user.username = "user@example.com"
    store.get_user_profile.return_value = user

    def replace(username, name, expires_at, created_by):
        naive = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        record = UserTokenRecord(id=9, name=name, token_prefix="ab12cd34", created_at=naive, created_by=created_by, expires_at=naive, last_used_at=None)
        return record, "mlf_ab12cd34_secret", replaced

    store.replace_user_token.side_effect = replace
    return store


async def _rotate(store, token_request=None):
    """Drive the endpoint and return the audit call."""
    with patch("mlflow_oidc_auth.routers.users.store", store):
        with patch("mlflow_oidc_auth.routers.users.emit_audit_event") as audit:
            result = await create_access_token(token_request=token_request, current_username="user@example.com", is_admin=False)
    assert result.status_code == 200
    audit.assert_called_once()
    return audit.call_args


class TestTokenRotateAudit:
    @pytest.mark.asyncio
    async def test_a_defaulted_expiry_is_recorded_as_such(self):
        call = await _rotate(_store())

        assert call[0][0] == "user.token_rotate"
        detail = call[1]["detail"]
        assert detail["expiration_defaulted"] is True
        assert detail["expiration"] is not None
        assert detail["name"] == "default" and detail["token_id"] == 9 and detail["token_prefix"] == "ab12cd34"

    @pytest.mark.asyncio
    async def test_a_requested_expiry_is_not_recorded_as_defaulted(self):
        wanted = datetime.now(timezone.utc) + timedelta(days=30)

        call = await _rotate(_store(), CreateAccessTokenRequest(expiration=wanted.isoformat()))

        assert call[1]["detail"]["expiration_defaulted"] is False
        assert call[1]["detail"]["expiration"].startswith(wanted.date().isoformat())

    @pytest.mark.asyncio
    @pytest.mark.parametrize("replaced", [True, False])
    async def test_whether_a_token_was_replaced_is_recorded(self, replaced):
        call = await _rotate(_store(replaced=replaced))

        assert call[1]["detail"]["replaced"] is replaced

    @pytest.mark.asyncio
    async def test_the_secret_is_never_audited(self):
        call = await _rotate(_store())

        assert "mlf_ab12cd34_secret" not in repr(call)
