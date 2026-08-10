"""Identity resolution policy (issue #309).

With more than one provider configured, ``users.username`` alone would let two IdPs asserting the
same email share an account. These tests are mostly about the attempts that must **not** reach a
user: the happy paths are few and the refusals are the reason the module exists.

Driven against a real store on SQLite, because the exact-match path depends on the unique
``(provider_id, subject)`` constraint that #333 created, and a fake repository would not have it.
"""

import pytest
from mlflow.exceptions import MlflowException

from mlflow_oidc_auth.identity_resolution import IdentityDecision, Resolution, resolve_identity
from mlflow_oidc_auth.provider_registry import ProviderConfig

ALICE = "alice@example.com"
BOB = "bob@example.com"


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    yield s
    s.engine.dispose()


@pytest.fixture
def resolve(store):
    """Resolve against the real repository and the real user table."""

    def _resolve(provider, subject, claims=None):
        return resolve_identity(
            provider=provider,
            subject=subject,
            claims=claims or {},
            identity_repo=store.user_identity_repo,
            user_lookup=store.has_user,
        )

    return _resolve


def subject_provider(provider_id="okta", **kwargs) -> ProviderConfig:
    return ProviderConfig(id=provider_id, audience="mlflow", identity_binding="subject", **kwargs)


def email_provider(provider_id="entra", domains=("example.com",), **kwargs) -> ProviderConfig:
    return ProviderConfig(id=provider_id, audience="mlflow", identity_binding="email", allowed_email_domains=tuple(domains), **kwargs)


class TestSubjectBinding:
    def test_an_unknown_subject_yields_create(self, store, resolve):
        decision = resolve(subject_provider(), "sub-1")

        assert decision.resolution is Resolution.CREATE
        assert decision.username is None

    def test_a_bound_subject_matches_its_user(self, store, resolve):
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("okta", "sub-1", ALICE)

        decision = resolve(subject_provider(), "sub-1")

        assert decision.resolution is Resolution.MATCHED
        assert decision.username == ALICE

    def test_the_same_subject_under_another_provider_does_not_match(self, store, resolve):
        """Subjects are only unique within a provider. Two IdPs both numbering their users
        from 1 must not collide."""
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("okta", "sub-1", ALICE)

        decision = resolve(subject_provider(provider_id="other-idp"), "sub-1")

        assert decision.resolution is Resolution.CREATE
        assert decision.username is None

    def test_a_matching_email_claim_cannot_reach_a_user(self, store, resolve):
        """The core of subject binding: email is never consulted, so asserting somebody else's
        address reaches nothing."""
        store.create_user(ALICE, "tok", "Alice")

        decision = resolve(subject_provider(), "attacker-sub", {"email": ALICE})

        assert decision.resolution is Resolution.CREATE
        assert decision.username is None

    def test_an_empty_subject_is_refused(self, store, resolve):
        for subject in ("", "   ", None):
            decision = resolve(subject_provider(), subject)
            assert decision.resolution is Resolution.REFUSED


class TestEmailBinding:
    def test_an_authorised_domain_links_to_an_existing_user(self, store, resolve):
        store.create_user(ALICE, "tok", "Alice")

        decision = resolve(email_provider(), "sub-1", {"email": ALICE})

        assert decision.resolution is Resolution.LINK
        assert decision.username == ALICE

    def test_an_authorised_domain_with_no_local_user_yields_create(self, store, resolve):
        decision = resolve(email_provider(), "sub-1", {"email": "newcomer@example.com"})

        assert decision.resolution is Resolution.CREATE

    def test_an_unauthorised_domain_is_refused_not_created(self, store, resolve):
        """Refused rather than 'no match'.

        Falling through to create would hand the caller an account for a domain the operator
        never authorised this provider to speak for.
        """
        store.create_user("victim@corp.example", "tok", "Victim")

        decision = resolve(email_provider(domains=("example.com",)), "sub-1", {"email": "victim@corp.example"})

        assert decision.resolution is Resolution.REFUSED
        assert decision.username is None
        assert "not authorised for email domain" in decision.reason

    def test_domain_matching_is_case_insensitive(self, store, resolve):
        store.create_user(ALICE, "tok", "Alice")

        decision = resolve(email_provider(domains=("EXAMPLE.COM",)), "sub-1", {"email": "Alice@Example.COM"})

        assert decision.resolution is Resolution.LINK
        assert decision.username == ALICE

    def test_a_missing_email_claim_is_refused(self, store, resolve):
        decision = resolve(email_provider(), "sub-1", {})

        assert decision.resolution is Resolution.REFUSED
        assert "no usable email" in decision.reason

    @pytest.mark.parametrize("email", ["a@b@example.com", "no-at-sign", "@example.com", "alice@"])
    def test_a_malformed_email_is_refused(self, store, resolve, email):
        """A second ``@`` parses differently depending on which end you read from, and a
        mismatch between this check and whatever reads the address later is how a domain
        allowlist gets bypassed."""
        decision = resolve(email_provider(), "sub-1", {"email": email})

        assert decision.resolution is Resolution.REFUSED

    def test_a_non_string_email_claim_is_refused(self, store, resolve):
        decision = resolve(email_provider(), "sub-1", {"email": ["alice@example.com"]})

        assert decision.resolution is Resolution.REFUSED


class TestCrossProviderTakeover:
    """The acceptance criterion this issue exists for."""

    def test_a_second_provider_cannot_link_by_email_to_an_owned_account(self, store, resolve):
        """Provider A owns alice. Provider B, authorised for the same domain, asserts her
        email. It must not inherit the account.

        Domain authorisation says B may speak for example.com; it does not say B may take over
        an account another provider already established.
        """
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("okta", "sub-a", ALICE)

        decision = resolve(email_provider(provider_id="rogue"), "sub-b", {"email": ALICE})

        assert decision.resolution is Resolution.REFUSED
        assert decision.username is None
        assert "already bound to provider" in decision.reason

    def test_the_owning_provider_may_still_link_a_second_identity(self, store, resolve):
        """The guard is about *other* providers, not about a provider adding an identity for a
        user it already owns."""
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("entra", "sub-old", ALICE)

        decision = resolve(email_provider(provider_id="entra"), "sub-new", {"email": ALICE})

        assert decision.resolution is Resolution.LINK
        assert decision.username == ALICE

    def test_an_existing_binding_wins_over_any_claim(self, store, resolve):
        """Once (provider, subject) names a user, no claim redirects it."""
        store.create_user(ALICE, "tok", "Alice")
        store.create_user(BOB, "tok", "Bob")
        store.user_identity_repo.link("entra", "sub-1", ALICE)

        decision = resolve(email_provider(provider_id="entra"), "sub-1", {"email": BOB})

        assert decision.resolution is Resolution.MATCHED
        assert decision.username == ALICE


class TestRepository:
    def test_linking_is_idempotent(self, store):
        store.create_user(ALICE, "tok", "Alice")

        assert store.user_identity_repo.link("okta", "sub-1", ALICE) is True
        assert store.user_identity_repo.link("okta", "sub-1", ALICE) is False

    def test_relinking_to_a_different_user_is_rejected(self, store):
        """The database constraint makes this impossible; the repository must not paper over it
        by re-pointing the row, which would be a takeover in one call."""
        store.create_user(ALICE, "tok", "Alice")
        store.create_user(BOB, "tok", "Bob")
        store.user_identity_repo.link("okta", "sub-1", ALICE)

        with pytest.raises(MlflowException, match="already bound to a different user"):
            store.user_identity_repo.link("okta", "sub-1", BOB)

        assert store.user_identity_repo.get_username_by_identity("okta", "sub-1") == ALICE

    def test_linking_to_an_unknown_user_is_rejected(self, store):
        with pytest.raises(MlflowException, match="unknown user"):
            store.user_identity_repo.link("okta", "sub-1", "ghost@example.com")

    def test_backfilled_identities_are_visible(self, store):
        """#333 gave every pre-existing user an identity under provider 'default'. A user
        created after the migration does not get one — that is #316's job at login."""
        store.create_user(ALICE, "tok", "Alice")

        assert store.user_identity_repo.get_username_by_identity("default", ALICE) is None

    def test_touch_last_login_sets_a_timestamp(self, store):
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("okta", "sub-1", ALICE)

        store.user_identity_repo.touch_last_login("okta", "sub-1")

        from mlflow_oidc_auth.db.models import SqlUserIdentity

        with store.engine.connect() as conn:
            row = conn.execute(SqlUserIdentity.__table__.select()).fetchone()
        assert row.last_login_at is not None

    def test_touch_last_login_on_a_missing_identity_is_a_no_op(self, store):
        """Best-effort by design: an identity that vanished between resolution and this call is
        not worth failing a login over."""
        store.user_identity_repo.touch_last_login("okta", "nope")

    def test_list_providers_for_username(self, store):
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("okta", "sub-1", ALICE)
        store.user_identity_repo.link("entra", "sub-2", ALICE)

        assert sorted(store.user_identity_repo.list_providers_for_username(ALICE)) == ["entra", "okta"]


class TestDecisionShape:
    def test_a_refusal_never_carries_a_username(self, store, resolve):
        """A caller that ignores ``resolution`` and reads ``username`` must get nothing, not the
        account it was refused."""
        store.create_user("victim@corp.example", "tok", "Victim")

        decision = resolve(email_provider(domains=("example.com",)), "s", {"email": "victim@corp.example"})

        assert decision.username is None
        assert decision.is_allowed is False

    def test_allowed_decisions_report_is_allowed(self):
        for resolution in (Resolution.MATCHED, Resolution.LINK, Resolution.CREATE):
            assert IdentityDecision(resolution).is_allowed is True

    def test_refusals_are_audited(self, store, resolve, monkeypatch):
        """Each refusal is a provider failing to reach an account it asked for — the signal an
        operator investigating a suspected takeover needs."""
        events = []
        monkeypatch.setattr(
            "mlflow_oidc_auth.identity_resolution.emit_audit_event",
            lambda event, **kwargs: events.append((event, kwargs)),
        )

        resolve(email_provider(domains=("example.com",)), "sub-1", {"email": "someone@corp.example"})

        assert events, "a refusal must be audited"
        event, kwargs = events[0]
        assert event == "identity.refused"
        assert kwargs["status"] == "denied"
        assert kwargs["resource_id"] == "entra"

    def test_audit_detail_does_not_carry_claim_contents(self, store, resolve, monkeypatch):
        """The reason is enough; copying claims into the audit log would put token contents in
        it."""
        events = []
        monkeypatch.setattr(
            "mlflow_oidc_auth.identity_resolution.emit_audit_event",
            lambda event, **kwargs: events.append((event, kwargs)),
        )

        resolve(email_provider(domains=("example.com",)), "sub-1", {"email": "x@corp.example", "secret_claim": "sensitive"})

        _, kwargs = events[0]
        assert "sensitive" not in str(kwargs)
