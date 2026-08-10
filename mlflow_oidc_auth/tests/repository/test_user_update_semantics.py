"""Argument semantics of ``UserRepository.update`` (issue #338).

Two defects shared one root cause: what "argument not supplied" meant was inconsistent with the
method's own parameter defaults.

* ``is_admin`` / ``is_service_account`` defaulted to ``False`` while the guards tested for
  ``None``, so omitting them cleared the flags instead of preserving them.
* ``password_expiration`` was only ever assigned when supplied, so a rotated token inherited the
  previous token's expiry — and since ``authenticate`` checks expiry before comparing the hash, a
  token rotated after the old one expired was rejected on its first use.

The rule these tests pin: omitted means untouched, except that replacing the secret also replaces
its lifetime with exactly the one supplied.
"""

from datetime import datetime, timedelta, timezone

import pytest

TOKEN = "aB3dE6gH9jK2mN5pQ8sT1vW4"  # shaped like generate_token() output; only ever in a tmp db
ROTATED = "zY9xW8vU7tS6rQ5pO4nM3lK2"


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


class TestRotationDoesNotInheritExpiry:
    """A newly issued secret must never arrive already dead."""

    def test_rotating_an_expired_token_yields_a_usable_one(self, store):
        """The headline bug: the new token was rejected on its first use.

        Reachable through the access-token endpoint whenever the request body omits
        ``expiration``, which is the default path for direct API and SDK callers.
        """
        store.create_user("exp@example.com", TOKEN, "Exp User")
        store.update_user(username="exp@example.com", password=TOKEN, password_expiration=_past())
        assert store.authenticate_user("exp@example.com", TOKEN) is False, "precondition: the old token is expired"

        store.update_user(username="exp@example.com", password=ROTATED)

        assert store.authenticate_user("exp@example.com", ROTATED) is True

    def test_rotating_clears_a_past_expiry(self, store):
        store.create_user("clr@example.com", TOKEN, "Clr User")
        store.update_user(username="clr@example.com", password=TOKEN, password_expiration=_past())

        store.update_user(username="clr@example.com", password=ROTATED)

        assert store.get_user_profile("clr@example.com").password_expiration is None

    def test_rotating_clears_a_future_expiry_too(self, store):
        """Omitting the expiration means "no expiry", not "keep whatever was there".

        The widening is deliberate and is recorded in the audit event emitted by the router; see
        ``TestTokenRotateAudit`` in tests/routers.
        """
        store.create_user("fut@example.com", TOKEN, "Fut User")
        store.update_user(username="fut@example.com", password=TOKEN, password_expiration=_future())

        store.update_user(username="fut@example.com", password=ROTATED)

        assert store.get_user_profile("fut@example.com").password_expiration is None

    def test_rotating_with_an_expiration_applies_exactly_that_one(self, store):
        store.create_user("set@example.com", TOKEN, "Set User")
        store.update_user(username="set@example.com", password=TOKEN, password_expiration=_past())
        wanted = _future().replace(microsecond=0)

        store.update_user(username="set@example.com", password=ROTATED, password_expiration=wanted)

        stored = store.get_user_profile("set@example.com").password_expiration
        assert stored is not None
        assert stored.replace(tzinfo=timezone.utc) == wanted

    def test_an_explicit_past_expiration_is_still_honoured(self, store):
        """The negative case: the fix must not turn into "ignore expiry".

        A caller that deliberately supplies a past expiration is revoking the credential, and
        that must still take effect.
        """
        store.create_user("rev@example.com", TOKEN, "Rev User")

        store.update_user(username="rev@example.com", password=ROTATED, password_expiration=_past())

        assert store.authenticate_user("rev@example.com", ROTATED) is False


class TestNonRotatingUpdatesLeaveExpiryAlone:
    """Group sync and flag changes must not disturb a credential's lifetime."""

    def test_updating_only_flags_preserves_a_future_expiry(self, store):
        store.create_user("keep@example.com", TOKEN, "Keep User")
        wanted = _future().replace(microsecond=0)
        store.update_user(username="keep@example.com", password=TOKEN, password_expiration=wanted)

        store.update_user(username="keep@example.com", is_admin=True)

        stored = store.get_user_profile("keep@example.com").password_expiration
        assert stored is not None
        assert stored.replace(tzinfo=timezone.utc) == wanted

    def test_setting_only_an_expiration_still_works(self, store):
        store.create_user("only@example.com", TOKEN, "Only User")

        store.update_user(username="only@example.com", password_expiration=_past())

        assert store.authenticate_user("only@example.com", TOKEN) is False


class TestOmittedFlagsArePreserved:
    """Omitting a flag must leave it as it was, not clear it."""

    def test_repo_update_with_only_a_password_preserves_admin(self, store):
        """The direct-repository call that silently demoted an admin."""
        store.create_user("adm@example.com", TOKEN, "Adm User", is_admin=True, is_service_account=True)

        store.user_repo.update(username="adm@example.com", password=ROTATED)

        profile = store.get_user_profile("adm@example.com")
        assert profile.is_admin is True
        assert profile.is_service_account is True

    def test_repo_update_with_only_an_expiration_preserves_admin(self, store):
        store.create_user("adm2@example.com", TOKEN, "Adm2 User", is_admin=True, is_service_account=True)

        store.user_repo.update(username="adm2@example.com", password_expiration=_future())

        profile = store.get_user_profile("adm2@example.com")
        assert profile.is_admin is True
        assert profile.is_service_account is True

    def test_store_update_with_only_a_password_preserves_admin(self, store):
        """The path that was already safe, pinned so it stays that way."""
        store.create_user("adm3@example.com", TOKEN, "Adm3 User", is_admin=True, is_service_account=True)

        store.update_user(username="adm3@example.com", password=ROTATED)

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
        s.create_user("dem@example.com", TOKEN, "Dem User", is_admin=True, is_service_account=True)
        # A second active admin, so demotion is not blocked by the last-active-admin invariant
        # (#311). The point here is that an explicit False still applies, not that the store
        # will let a deployment strand itself without an administrator.
        s.create_user("other-admin@example.com", TOKEN, "Other Admin", is_admin=True)

        s.update_user(username="dem@example.com", **{flag: False})

        assert getattr(s.get_user_profile("dem@example.com"), flag) is False
