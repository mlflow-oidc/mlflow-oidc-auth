"""Argument semantics of ``UserRepository.update`` and of replacing a token (issues #338, #189).

Two defects shared one root cause: what "argument not supplied" meant was inconsistent with the
method's own parameter defaults.

* ``is_admin`` / ``is_service_account`` defaulted to ``False`` while the guards tested for
  ``None``, so omitting them cleared the flags instead of preserving them.
* a rotated secret inherited the previous one's expiry, so a token rotated after the old one
  expired was rejected on its first use.

Since #189 a secret is a row in ``user_tokens`` and replacing it issues a new row with exactly the
expiry requested. The rules these tests pin: omitted means untouched, a replaced token never
inherits a lifetime, and ``revoke_tokens`` removes every token.
"""

from datetime import datetime, timedelta, timezone

import pytest

from mlflow_oidc_auth.tests.token_helpers import issue_token, set_known_token

TOKEN = "aB3dE6gH9jK2mN5pQ8sT1vW4"  # shaped like a pre-#189 secret; only ever in a tmp db


@pytest.fixture
def store(tmp_path):
    """A real store on a temporary SQLite database."""
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    return s


def _past() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=1)


def _future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=30)


class TestReplacingATokenNeverInheritsItsExpiry:
    """A newly issued token must never arrive already dead (issue #338), and must carry exactly
    the lifetime it was issued with (issue #189)."""

    def test_replacing_an_expired_default_token_yields_a_usable_one(self, store):
        """The #338 headline bug, in its #189 form: the replacement is usable on first use."""
        store.create_user("exp@example.com", "Exp User")
        set_known_token(store, "exp@example.com", TOKEN, expires_at=_past().replace(tzinfo=None))
        assert store.authenticate_user("exp@example.com", TOKEN) is False, "precondition: the old token is expired"

        _, plaintext, _ = store.replace_user_token("exp@example.com", "default", _future(), created_by=None)

        assert [r.name for r in store.list_user_tokens("exp@example.com")] == ["default"]
        assert store.authenticate_user("exp@example.com", plaintext) is True
        assert store.authenticate_user("exp@example.com", TOKEN) is False

    def test_replacing_applies_exactly_the_requested_expiry(self, store):
        store.create_user("fut@example.com", "Fut User")
        set_known_token(store, "fut@example.com", TOKEN)
        wanted = _future().replace(microsecond=0)

        record, _, _ = store.replace_user_token("fut@example.com", "default", wanted, created_by=None)

        assert record.expires_at.replace(tzinfo=timezone.utc) == wanted

    def test_a_past_expiration_is_refused_not_stored(self, store):
        from mlflow.exceptions import MlflowException

        store.create_user("rev@example.com", "Rev User")

        with pytest.raises(MlflowException):
            store.replace_user_token("rev@example.com", "default", _past(), created_by=None)

        assert store.list_user_tokens("rev@example.com") == []


class TestNonCredentialUpdatesLeaveTokensAlone:
    """Group sync and flag changes must not disturb a user's tokens."""

    def test_updating_only_flags_keeps_every_token(self, store):
        store.create_user("keep@example.com", "Keep User")
        plaintext = issue_token(store, "keep@example.com", name="ci")

        store.update_user(username="keep@example.com", is_admin=True)

        assert store.authenticate_user("keep@example.com", plaintext) is True

    def test_revoke_tokens_deletes_every_token(self, store):
        store.create_user("rv@example.com", "Rv User")
        first = issue_token(store, "rv@example.com", name="a")
        second = issue_token(store, "rv@example.com", name="b")

        store.update_user(username="rv@example.com", revoke_tokens=True)

        assert store.list_user_tokens("rv@example.com") == []
        assert store.authenticate_user("rv@example.com", first) is False
        assert store.authenticate_user("rv@example.com", second) is False


class TestOmittedFlagsArePreserved:
    """Omitting a flag must leave it as it was, not clear it."""

    def test_repo_update_with_only_revoke_tokens_preserves_admin(self, store):
        """The direct-repository call that silently demoted an admin."""
        store.create_user("adm@example.com", "Adm User", is_admin=True, is_service_account=True)

        store.user_repo.update(username="adm@example.com", revoke_tokens=True)

        profile = store.get_user_profile("adm@example.com")
        assert profile.is_admin is True
        assert profile.is_service_account is True

    def test_repo_update_with_only_a_display_name_preserves_admin(self, store):
        store.create_user("adm2@example.com", "Adm2 User", is_admin=True, is_service_account=True)

        store.user_repo.update(username="adm2@example.com", display_name="Renamed")

        profile = store.get_user_profile("adm2@example.com")
        assert profile.is_admin is True
        assert profile.is_service_account is True

    def test_store_update_with_only_revoke_tokens_preserves_admin(self, store):
        """The path that was already safe, pinned so it stays that way."""
        store.create_user("adm3@example.com", "Adm3 User", is_admin=True, is_service_account=True)

        store.update_user(username="adm3@example.com", revoke_tokens=True)

        profile = store.get_user_profile("adm3@example.com")
        assert profile.is_admin is True
        assert profile.is_service_account is True

    @pytest.mark.parametrize("flag", ["is_admin", "is_service_account"])
    def test_flags_can_still_be_set_false_explicitly(self, flag):
        """Preserving on omission must not make demotion impossible."""
        # Built per-parametrisation rather than via the fixture so each case gets its own db.
        import tempfile
        from pathlib import Path

        from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

        s = SqlAlchemyStore()
        s.init_db(f"sqlite:///{Path(tempfile.mkdtemp()) / 'auth.db'}")
        s.create_user("dem@example.com", "Dem User", is_admin=True, is_service_account=True)
        # A second active admin, so demotion is not blocked by the last-active-admin invariant
        # (#311). The point here is that an explicit False still applies, not that the store
        # will let a deployment strand itself without an administrator.
        s.create_user("other-admin@example.com", "Other Admin", is_admin=True)

        s.update_user(username="dem@example.com", **{flag: False})

        assert getattr(s.get_user_profile("dem@example.com"), flag) is False
