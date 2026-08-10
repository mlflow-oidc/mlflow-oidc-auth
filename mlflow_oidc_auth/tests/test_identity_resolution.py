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


def verified(email: str) -> dict:
    """Claims for an address the provider states it has verified.

    Spelled out at every call site on purpose: linking on an *unverified* address is the
    account-takeover shape this module has to refuse, so a test that links must be visibly
    asserting the verified case.
    """
    return {"email": email, "email_verified": True}


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

        decision = resolve(subject_provider(), "attacker-sub", verified(ALICE))

        assert decision.resolution is Resolution.CREATE
        assert decision.username is None

    def test_an_empty_subject_is_refused(self, store, resolve):
        for subject in ("", "   ", None):
            decision = resolve(subject_provider(), subject)
            assert decision.resolution is Resolution.REFUSED


class TestEmailBinding:
    def test_an_authorised_domain_links_to_an_existing_user(self, store, resolve):
        store.create_user(ALICE, "tok", "Alice")

        decision = resolve(email_provider(), "sub-1", verified(ALICE))

        assert decision.resolution is Resolution.LINK
        assert decision.username == ALICE

    def test_an_authorised_domain_with_no_local_user_yields_create(self, store, resolve):
        decision = resolve(email_provider(), "sub-1", verified("newcomer@example.com"))

        assert decision.resolution is Resolution.CREATE

    def test_an_unauthorised_domain_is_refused_not_created(self, store, resolve):
        """Refused rather than 'no match'.

        Falling through to create would hand the caller an account for a domain the operator
        never authorised this provider to speak for.
        """
        store.create_user("victim@corp.example", "tok", "Victim")

        decision = resolve(email_provider(domains=("example.com",)), "sub-1", verified("victim@corp.example"))

        assert decision.resolution is Resolution.REFUSED
        assert decision.username is None
        assert "not authorised for email domain" in decision.reason

    def test_domain_matching_is_case_insensitive(self, store, resolve):
        store.create_user(ALICE, "tok", "Alice")

        decision = resolve(email_provider(domains=("EXAMPLE.COM",)), "sub-1", {"email": "Alice@Example.COM", "email_verified": True})

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
        decision = resolve(email_provider(), "sub-1", {"email": email, "email_verified": True})

        assert decision.resolution is Resolution.REFUSED

    def test_a_non_string_email_claim_is_refused(self, store, resolve):
        decision = resolve(email_provider(), "sub-1", {"email": ["alice@example.com"], "email_verified": True})

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

        decision = resolve(email_provider(provider_id="rogue"), "sub-b", verified(ALICE))

        assert decision.resolution is Resolution.REFUSED
        assert decision.username is None
        assert "already bound to provider" in decision.reason

    def test_the_owning_provider_may_still_link_a_second_identity(self, store, resolve):
        """The guard is about *other* providers, not about a provider adding an identity for a
        user it already owns."""
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("entra", "sub-old", ALICE)

        decision = resolve(email_provider(provider_id="entra"), "sub-new", verified(ALICE))

        assert decision.resolution is Resolution.LINK
        assert decision.username == ALICE

    def test_an_existing_binding_wins_over_any_claim(self, store, resolve):
        """Once (provider, subject) names a user, no claim redirects it."""
        store.create_user(ALICE, "tok", "Alice")
        store.create_user(BOB, "tok", "Bob")
        store.user_identity_repo.link("entra", "sub-1", ALICE)

        decision = resolve(email_provider(provider_id="entra"), "sub-1", verified(BOB))

        assert decision.resolution is Resolution.MATCHED
        assert decision.username == ALICE


class TestUnverifiedEmail:
    """Linking on an unverified address is the classic "Sign in with X" takeover.

    ``allowed_email_domains`` bounds *which* domains a provider may speak for; it does nothing
    inside an authorised one. If the provider has not verified the address, an attacker who
    registers at that IdP under a colleague's email is handed the colleague's account.
    Raised in review of #345.
    """

    @pytest.mark.parametrize("claims", [{"email": ALICE}, {"email": ALICE, "email_verified": False}, {"email": ALICE, "email_verified": None}])
    def test_an_unverified_email_never_links(self, store, resolve, claims):
        store.create_user(ALICE, "tok", "Alice")

        decision = resolve(email_provider(), "attacker-sub", claims)

        assert decision.resolution is Resolution.REFUSED
        assert decision.username is None
        assert "email_verified" in decision.reason

    @pytest.mark.parametrize("value", ["true", "True", 1, "yes"])
    def test_only_a_literal_true_counts_as_verified(self, store, resolve, value):
        """Truthy stand-ins are not proof. A provider emitting the string "false" would
        otherwise read as verified."""
        store.create_user(ALICE, "tok", "Alice")

        decision = resolve(email_provider(), "sub-1", {"email": ALICE, "email_verified": value})

        assert decision.resolution is Resolution.REFUSED

    def test_an_unverified_email_is_refused_rather_than_creating(self, store, resolve):
        """Not CREATE either: an account named for an unverified address is pre-registration
        takeover — claim the name first, and the real owner logs into the attacker's account."""
        decision = resolve(email_provider(), "attacker-sub", {"email": "victim@example.com"})

        assert decision.resolution is Resolution.REFUSED

    def test_subject_binding_does_not_care_about_email_verified(self, store, resolve):
        """It never reads email at all, so the flag is irrelevant there."""
        decision = resolve(subject_provider(), "sub-1", {"email": ALICE, "email_verified": False})

        assert decision.resolution is Resolution.CREATE


class TestUsernameIsNamedByTheEmail:
    """Under email binding the account is named by the address, and only by it.

    Authorising a domain says the provider may speak for addresses there; it does not license
    naming some other account. Raised in review of #345.
    """

    def test_a_username_derived_from_other_claims_is_refused(self, store, resolve):
        """The hole this closes: presenting a verified address of one's own alongside somebody
        else's username would otherwise reach their account."""
        store.create_user("alice", "tok", "Alice")

        decision = resolve_identity(
            provider=email_provider(),
            subject="attacker-sub",
            claims=verified("attacker@example.com"),
            identity_repo=store.user_identity_repo,
            user_lookup=store.has_user,
            username="alice",
        )

        assert decision.resolution is Resolution.REFUSED
        assert "names accounts by their email address" in decision.reason

    def test_a_username_matching_the_email_is_accepted(self, store, resolve):
        store.create_user(ALICE, "tok", "Alice")

        decision = resolve_identity(
            provider=email_provider(),
            subject="sub-1",
            claims=verified(ALICE),
            identity_repo=store.user_identity_repo,
            user_lookup=store.has_user,
            username=ALICE,
        )

        assert decision.resolution is Resolution.LINK
        assert decision.username == ALICE

    def test_username_comparison_is_case_insensitive(self, store, resolve):
        store.create_user(ALICE, "tok", "Alice")

        decision = resolve_identity(
            provider=email_provider(),
            subject="sub-1",
            claims=verified(ALICE),
            identity_repo=store.user_identity_repo,
            user_lookup=store.has_user,
            username="Alice@Example.com",
        )

        assert decision.resolution is Resolution.LINK


class TestLinkEnforcesTheGuardItself:
    """The cross-provider rule has to hold at the write, not only at the decision.

    ``user_identity_repo`` is public on the store, so a caller reaching it directly used to
    bypass the check entirely; and a caller that did resolve first still had a window in which a
    concurrent login could bind another provider before it wrote. Raised in review of #345.
    """

    def test_a_second_provider_cannot_be_bound_by_default(self, store):
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("okta", "sub-a", ALICE)

        with pytest.raises(MlflowException, match="already bound to provider"):
            store.user_identity_repo.link("rogue", "sub-b", ALICE)

        assert store.user_identity_repo.list_providers_for_username(ALICE) == ["okta"]

    def test_the_owning_provider_may_add_another_subject(self, store):
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("okta", "sub-a", ALICE)

        assert store.user_identity_repo.link("okta", "sub-b", ALICE) is True

    def test_deliberate_account_linking_remains_possible(self, store):
        """A person genuinely holding identities at two IdPs is a real case — it just has to be
        an explicit decision at the call site rather than something that happens by omission."""
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("okta", "sub-a", ALICE)

        assert store.user_identity_repo.link("entra", "sub-b", ALICE, allow_additional_provider=True) is True
        assert sorted(store.user_identity_repo.list_providers_for_username(ALICE)) == ["entra", "okta"]

    def test_the_write_refuses_even_when_resolution_was_skipped(self, store):
        """The bypass itself: no call to resolve_identity anywhere in this test."""
        store.create_user(ALICE, "tok", "Alice")
        store.user_identity_repo.link("entra", "sub-a", ALICE)

        with pytest.raises(MlflowException):
            store.user_identity_repo.link("attacker-idp", "sub-b", ALICE)


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
        store.user_identity_repo.link("entra", "sub-2", ALICE, allow_additional_provider=True)

        assert sorted(store.user_identity_repo.list_providers_for_username(ALICE)) == ["entra", "okta"]


class TestDecisionShape:
    def test_a_refusal_never_carries_a_username(self, store, resolve):
        """A caller that ignores ``resolution`` and reads ``username`` must get nothing, not the
        account it was refused."""
        store.create_user("victim@corp.example", "tok", "Victim")

        decision = resolve(email_provider(domains=("example.com",)), "s", verified("victim@corp.example"))

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

        resolve(email_provider(domains=("example.com",)), "sub-1", verified("someone@corp.example"))

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

        resolve(email_provider(domains=("example.com",)), "sub-1", {"email": "x@corp.example", "email_verified": True, "secret_claim": "sensitive"})

        _, kwargs = events[0]
        assert "sensitive" not in str(kwargs)
