"""Per-provider provisioning, group sync and admin source (issue #318).

These three decisions used to come from deployment-wide configuration, which is defensible with
one identity provider and is account takeover with two. Each case below is a policy combination
the registry can express, and the ones that matter most are the refusals: a provider that may not
create users, and a provider that may not claim a username someone else already answers to.
"""

import pytest

from mlflow_oidc_auth.identity_resolution import IdentityDecision, Resolution
from mlflow_oidc_auth.provider_registry import ProviderConfig
from mlflow_oidc_auth.provisioning_policy import admin_from_claims, apply_provisioning_policy, groups_to_apply

ADMIN_GROUPS = ["mlflow-admins"]


def provider(**overrides):
    fields = {"id": "entra", "type": "oidc", "audience": "mlflow", "issuer": "https://entra.invalid"}
    fields.update(overrides)
    return ProviderConfig(**fields)


def nobody_exists(_username):
    return False


def everybody_exists(_username):
    return True


class TestProvisioning:
    def test_jit_creates_a_new_principal(self):
        outcome = apply_provisioning_policy(
            provider(provisioning="jit"),
            IdentityDecision(Resolution.CREATE),
            derived_username="new@corp.com",
            user_exists=nobody_exists,
        )

        assert outcome.allowed is True
        assert outcome.create is True
        assert outcome.username == "new@corp.com"

    @pytest.mark.parametrize("policy", ["scim", "none"])
    def test_a_non_jit_provider_never_creates(self, policy):
        """The enterprise gate: the directory decides who exists, and login does not."""
        outcome = apply_provisioning_policy(
            provider(provisioning=policy),
            IdentityDecision(Resolution.CREATE),
            derived_username="new@corp.com",
            user_exists=nobody_exists,
        )

        assert outcome.allowed is False
        assert policy in outcome.reason

    @pytest.mark.parametrize("policy", ["scim", "none"])
    def test_a_known_user_still_signs_in(self, policy):
        """Not creating is not the same as not admitting."""
        outcome = apply_provisioning_policy(
            provider(provisioning=policy),
            IdentityDecision(Resolution.MATCHED, username="alice@corp.com"),
            derived_username="alice@corp.com",
            user_exists=everybody_exists,
        )

        assert outcome.allowed is True
        assert outcome.create is False
        assert outcome.username == "alice@corp.com"

    def test_a_refused_identity_is_never_upgraded_into_a_create(self):
        outcome = apply_provisioning_policy(
            provider(provisioning="jit"),
            IdentityDecision(Resolution.REFUSED, reason="email domain not allowed"),
            derived_username="mallory@evil.invalid",
            user_exists=nobody_exists,
        )

        assert outcome.allowed is False
        assert outcome.create is False
        assert "email domain" in outcome.reason


class TestOneProviderCannotClaimAnothersAccount:
    """The reason #318 had to land with #316: with two providers, an unbound identity whose
    claims name an existing user is a takeover attempt, not a new principal."""

    def test_an_unbound_identity_cannot_take_an_existing_username(self):
        outcome = apply_provisioning_policy(
            provider(id="partner-okta", provisioning="jit"),
            IdentityDecision(Resolution.CREATE),
            derived_username="alice@corp.com",
            user_exists=everybody_exists,
        )

        assert outcome.allowed is False
        assert "already belongs to another identity" in outcome.reason
        assert "partner-okta" in outcome.reason

    def test_the_same_identity_bound_already_is_fine(self):
        """Once bound, the account *is* theirs — that is what binding means."""
        outcome = apply_provisioning_policy(
            provider(id="partner-okta"),
            IdentityDecision(Resolution.MATCHED, username="alice@corp.com"),
            derived_username="alice@corp.com",
            user_exists=everybody_exists,
        )

        assert outcome.allowed is True

    def test_no_username_at_all_is_refused(self):
        outcome = apply_provisioning_policy(
            provider(),
            IdentityDecision(Resolution.CREATE),
            derived_username=None,
            user_exists=nobody_exists,
        )

        assert outcome.allowed is False


class TestGroupSync:
    def test_every_login_authoritative_replaces(self):
        """Today's behaviour, and the default."""
        groups = groups_to_apply(provider(), ["a", "b"], ["b", "c"], is_new_user=False)

        assert groups == ["entra:a", "entra:b"]

    def test_authoritative_genuinely_removes(self):
        """The acceptance criterion the issue calls out. Keycloak's FORCE mapper is add-only in
        practice, so a deployment expecting revocation to propagate gets it from here or nowhere."""
        groups = groups_to_apply(provider(group_sync_mode="authoritative"), ["a"], ["entra:a", "entra:revoked"], is_new_user=False)

        assert "entra:revoked" not in groups

    def test_additive_never_removes(self):
        """For a deployment where some memberships come from elsewhere — SCIM, or by hand — and
        the token only knows about its own."""
        groups = groups_to_apply(provider(group_sync_mode="additive"), ["a"], ["kept-by-scim"], is_new_user=False)

        assert set(groups) == {"entra:a", "kept-by-scim"}

    def test_none_leaves_membership_alone(self):
        assert groups_to_apply(provider(group_sync="none"), ["a"], ["b"], is_new_user=False) is None

    def test_first_login_applies_only_on_creation(self):
        first = groups_to_apply(provider(group_sync="first_login"), ["a"], [], is_new_user=True)
        later = groups_to_apply(provider(group_sync="first_login"), ["a", "b"], ["a"], is_new_user=False)

        assert first == ["entra:a"]
        assert later is None

    def test_duplicates_are_collapsed(self):
        assert groups_to_apply(provider(), ["a", "a", "b"], [], is_new_user=True) == ["entra:a", "entra:b"]

    def test_blank_group_names_are_dropped(self):
        assert groups_to_apply(provider(), ["a", "", None], [], is_new_user=True) == ["entra:a"]


class TestAdminSource:
    def test_claims_confer_admin(self):
        assert admin_from_claims(provider(admin_source="claims"), ["mlflow-admins"], ADMIN_GROUPS) is True

    def test_a_provider_with_no_admin_source_never_does(self):
        """The answer for a partner or contractor tenant whose group names you do not control:
        it can assert whatever it likes and still confer nothing."""
        assert admin_from_claims(provider(admin_source="none"), ["mlflow-admins"], ADMIN_GROUPS) is False

    def test_a_non_member_is_not_an_admin(self):
        assert admin_from_claims(provider(), ["engineering"], ADMIN_GROUPS) is False


class TestTheDefaultProviderIsUnchanged:
    """A deployment that configures nothing must behave exactly as before."""

    @staticmethod
    def _default():
        return ProviderConfig(id="default", type="oidc")

    def test_it_creates_on_first_login(self):
        outcome = apply_provisioning_policy(self._default(), IdentityDecision(Resolution.CREATE), derived_username="a@b.c", user_exists=nobody_exists)

        assert (outcome.allowed, outcome.create) == (True, True)

    def test_it_replaces_groups_on_every_login(self):
        assert groups_to_apply(self._default(), ["a"], ["stale"], is_new_user=False) == ["a"]

    def test_it_reads_admin_from_claims(self):
        assert admin_from_claims(self._default(), ["mlflow-admins"], ADMIN_GROUPS) is True


class TestASecondProviderCannotJoinLocalGroupsByName:
    """Group names are the permission boundary: ``set_user_groups`` joins by name and
    ``populate_groups`` creates whatever is missing."""

    def test_a_second_providers_groups_are_namespaced(self):
        groups = groups_to_apply(provider(id="partner"), ["finance-ds"], [], is_new_user=True)

        assert groups == ["partner:finance-ds"], "an unnamespaced claim would join the local finance-ds group"

    def test_the_default_providers_groups_are_not(self):
        """Those are the names every existing deployment already has."""
        default = ProviderConfig(id="default", type="oidc")

        assert groups_to_apply(default, ["finance-ds"], [], is_new_user=True) == ["finance-ds"]

    def test_a_second_provider_cannot_reach_the_admin_group_by_name_either(self):
        groups = groups_to_apply(provider(id="partner"), ["mlflow-admin"], [], is_new_user=True)

        assert groups == ["partner:mlflow-admin"]


class TestAdoptingAnAccountFromBeforeIdentitiesWereRecorded:
    """Every user of every upgraded deployment takes this path on their first login.

    The Phase 0 backfill wrote ``subject = username`` because that was all it had, and a real
    ``sub`` is not a username — so the first login after upgrading resolves to CREATE and finds
    the name taken. Without adoption that refuses *every existing user, including every
    administrator*, with no way back that does not involve the database.
    """

    def test_the_default_provider_adopts_an_unbound_account(self):
        outcome = apply_provisioning_policy(
            ProviderConfig(id="default", type="oidc"),
            IdentityDecision(Resolution.CREATE),
            derived_username="alice@corp.com",
            user_exists=everybody_exists,
            providers_bound_to=lambda _name: [],
        )

        assert outcome.allowed is True
        assert outcome.create is False
        assert outcome.username == "alice@corp.com"

    def test_it_does_not_adopt_an_account_another_provider_owns(self):
        outcome = apply_provisioning_policy(
            ProviderConfig(id="default", type="oidc"),
            IdentityDecision(Resolution.CREATE),
            derived_username="mallory@partner.com",
            user_exists=everybody_exists,
            providers_bound_to=lambda _name: ["partner"],
        )

        assert outcome.allowed is False

    def test_a_second_provider_never_adopts(self):
        """Adoption is safe only for the provider that named the account in the first place."""
        outcome = apply_provisioning_policy(
            provider(id="partner"),
            IdentityDecision(Resolution.CREATE),
            derived_username="alice@corp.com",
            user_exists=everybody_exists,
            providers_bound_to=lambda _name: [],
        )

        assert outcome.allowed is False

    def test_an_unreadable_binding_set_refuses_rather_than_adopts(self):
        """Fail closed: "cannot tell" must not read as "bound to nobody"."""
        outcome = apply_provisioning_policy(
            ProviderConfig(id="default", type="oidc"),
            IdentityDecision(Resolution.CREATE),
            derived_username="alice@corp.com",
            user_exists=everybody_exists,
            providers_bound_to=lambda _name: ["<unknown>"],
        )

        assert outcome.allowed is False
