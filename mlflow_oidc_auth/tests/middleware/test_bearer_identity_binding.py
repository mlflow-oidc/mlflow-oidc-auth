"""Bearer authentication holds a token to the identity decision interactive login makes (#309).

With more than one token-validating provider, ``(provider, sub)`` decides which local user a token
reaches — never the email or username it asserts — and a name another provider's identity owns is
refused. A single-provider deployment has one identity space and is unchanged.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

import mlflow_oidc_auth.store as store_module
from mlflow_oidc_auth.config import config
from mlflow_oidc_auth.middleware import auth_middleware
from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware
from mlflow_oidc_auth.provider_registry import ProviderConfig, RegistryLoadResult

ADMIN = "admin@corp.example"
LEGACY = "legacy@corp.example"
BOB = "bob@partner.example"


def _provider(provider_id, **overrides):
    fields = {
        "id": provider_id,
        "type": "oidc",
        "audience": "mlflow",
        "issuer": f"https://{provider_id}.invalid",
        "provisioning": "jit",
        "group_sync": "every_login",
        "group_sync_mode": "authoritative",
        "admin_source": "claims" if provider_id == "default" else "none",
    }
    fields.update(overrides)
    return ProviderConfig(**fields)


DEFAULT = _provider("default")
PARTNER = _provider("partner")


@pytest.fixture
def store(tmp_path):
    from mlflow_oidc_auth.sqlalchemy_store import SqlAlchemyStore

    s = SqlAlchemyStore()
    s.init_db(f"sqlite:///{tmp_path / 'auth.db'}")
    s.create_user(ADMIN, "Admin", is_admin=True)
    s.user_identity_repo.link("default", "corp-admin-sub", ADMIN)
    s.create_user(LEGACY, "Legacy")  # from before identities were recorded: no binding
    s.create_user(BOB, "Bob")
    s.user_identity_repo.link("partner", "partner-bob-sub", BOB)
    previous = object.__getattribute__(store_module.store, "_instance")
    object.__setattr__(store_module.store, "_instance", s)
    yield s
    object.__setattr__(store_module.store, "_instance", previous)
    s.engine.dispose()


@pytest.fixture(autouse=True)
def fresh_cache():
    from mlflow_oidc_auth.utils import bearer_identity_cache

    bearer_identity_cache._cache = None
    yield
    bearer_identity_cache._cache = None


@pytest.fixture
def providers(monkeypatch):
    def configure(*entries):
        monkeypatch.setattr(config, "AUTH_PROVIDERS", RegistryLoadResult(providers=list(entries), errors=[], source="test"))

    configure(DEFAULT, PARTNER)
    monkeypatch.setattr(config, "OIDC_PROVISION_ON_BEARER_AUTH", False)
    monkeypatch.setattr(config, "OIDC_USERNAME_FIELD", ["email", "preferred_username"])
    return configure


def _enable_provisioning(monkeypatch):
    import mlflow_oidc_auth.auth as auth_module

    monkeypatch.setattr(config, "OIDC_PROVISION_ON_BEARER_AUTH", True)
    monkeypatch.setattr(config, "OIDC_GROUP_DETECTION_PLUGIN", None)
    monkeypatch.setattr(config, "OIDC_GROUPS_ATTRIBUTE", "groups")
    monkeypatch.setattr(config, "OIDC_GROUP_NAME", ["mlflow-users"])
    monkeypatch.setattr(config, "OIDC_GROUP_NAME_PATTERN", [])
    monkeypatch.setattr(config, "OIDC_ADMIN_GROUP_NAME", ["mlflow-admins"])
    monkeypatch.setattr(auth_module, "resolve_token_provider", lambda token: PARTNER)


def authenticate(provider, claims):
    """Run the bearer path for a token ``provider`` validated with ``claims``."""
    middleware = AuthMiddleware(app=MagicMock())
    with (
        patch.object(auth_middleware, "validate_token", return_value=claims),
        patch.object(AuthMiddleware, "_provider_for", return_value=provider),
    ):
        ok, username, _ = asyncio.run(middleware._authenticate_bearer_token("Bearer token"))
    return username if ok else None


class TestAnotherProviderCannotReachAnAccountByName:
    def test_asserting_an_existing_users_email_is_refused(self, store, providers):
        assert authenticate(PARTNER, {"sub": "partner-mallory", "email": ADMIN}) is None

    def test_a_legacy_account_without_a_binding_is_not_adopted_by_another_provider(self, store, providers):
        assert authenticate(PARTNER, {"sub": "partner-mallory", "email": LEGACY}) is None

    def test_a_token_without_a_subject_is_refused(self, store, providers):
        assert authenticate(PARTNER, {"email": BOB}) is None


class TestTheIdentityDecides:
    def test_a_bound_identity_reaches_its_own_user_whatever_the_token_names(self, store, providers):
        assert authenticate(PARTNER, {"sub": "partner-bob-sub", "email": ADMIN}) == BOB

    def test_the_default_provider_reaches_its_bound_user(self, store, providers):
        assert authenticate(DEFAULT, {"sub": "corp-admin-sub", "email": ADMIN}) == ADMIN

    def test_the_default_provider_adopts_an_account_from_before_identities(self, store, providers):
        assert authenticate(DEFAULT, {"sub": "corp-legacy-sub", "email": LEGACY}) == LEGACY

    def test_the_default_provider_cannot_take_an_account_another_provider_owns(self, store, providers):
        assert authenticate(DEFAULT, {"sub": "corp-someone", "email": BOB}) is None

    def test_a_new_principal_without_provisioning_is_refused(self, store, providers):
        """No account yet and nothing to create one: the user would not exist downstream either,
        and accepting the name here would let it reach an account created in the meantime."""
        assert authenticate(PARTNER, {"sub": "partner-new", "email": "new@partner.example"}) is None

    def test_an_account_another_identity_claims_meanwhile_is_refused(self, store, providers, monkeypatch):
        """The decision to create is re-checked after provisioning: only an account bound to this
        identity is served."""
        monkeypatch.setattr(config, "OIDC_PROVISION_ON_BEARER_AUTH", True)

        def someone_else_claims_it(self, username, token, payload):
            store.create_user(username, "Raced")
            store.user_identity_repo.link("default", "corp-raced", username)

        monkeypatch.setattr(AuthMiddleware, "_maybe_provision_bearer_user", someone_else_claims_it)

        assert authenticate(PARTNER, {"sub": "partner-racer", "email": "raced@fresh.example"}) is None

    def test_a_failed_bind_on_provisioning_refuses_the_token(self, store, providers, monkeypatch):
        _enable_provisioning(monkeypatch)
        monkeypatch.setattr(store.user_identity_repo, "link", MagicMock(side_effect=RuntimeError("db down")))

        assert authenticate(PARTNER, {"sub": "partner-erin", "email": "erin@partner.example", "groups": ["mlflow-users"]}) is None


class TestEveryRegistryShapeWithMoreThanOneProvider:
    def test_a_saml_login_with_a_single_token_provider_is_still_protected(self, store, providers):
        """One token provider is not one identity space: a SAML login binds identities too."""
        providers(_provider("corp", type="saml", audience=None, issuer=None), PARTNER)

        assert authenticate(PARTNER, {"sub": "partner-mallory", "email": ADMIN}) is None

    def test_the_default_provider_beside_kubernetes_is_held_to_its_identity(self, store, providers):
        providers(DEFAULT, _provider("cluster", type="k8s"))

        assert authenticate(DEFAULT, {"sub": "corp-someone", "email": BOB}) is None
        assert authenticate(DEFAULT, {"sub": "corp-admin-sub", "email": ADMIN}) == ADMIN

    def test_an_unidentified_provider_is_refused(self, store, providers):
        assert authenticate(None, {"sub": "x", "email": BOB}) is None


class TestEmailBinding:
    PARTNER_BY_EMAIL = _provider("partner", identity_binding="email", allowed_email_domains=["partner.example"])

    def test_a_verified_address_in_an_allowed_domain_reaches_its_unbound_account(self, store, providers):
        store.create_user("frank@partner.example", "Frank")
        providers(DEFAULT, self.PARTNER_BY_EMAIL)

        assert authenticate(self.PARTNER_BY_EMAIL, {"sub": "p-frank", "email": "frank@partner.example", "email_verified": True}) == "frank@partner.example"

    def test_an_address_outside_the_allowed_domains_is_refused(self, store, providers):
        providers(DEFAULT, self.PARTNER_BY_EMAIL)

        assert authenticate(self.PARTNER_BY_EMAIL, {"sub": "p-x", "email": ADMIN, "email_verified": True}) is None

    def test_an_unverified_address_is_refused(self, store, providers):
        store.create_user("gina@partner.example", "Gina")
        providers(DEFAULT, self.PARTNER_BY_EMAIL)

        assert authenticate(self.PARTNER_BY_EMAIL, {"sub": "p-gina", "email": "gina@partner.example"}) is None


class TestASingleProviderDeploymentIsUnchanged:
    def test_the_claimed_name_is_the_user_and_no_identity_is_looked_up(self, store, providers):
        providers(DEFAULT)
        with patch.object(store.user_identity_repo, "get_username_by_identity") as lookup:
            assert authenticate(DEFAULT, {"sub": "anything", "email": BOB}) == BOB
        lookup.assert_not_called()


class TestAPartnerCannotClaimAddressesInAnotherProvidersDomain:
    def test_provisioning_an_account_in_the_corporate_domain_is_refused(self, store, providers, monkeypatch):
        _enable_provisioning(monkeypatch)

        assert authenticate(PARTNER, {"sub": "partner-dave", "email": "dave@corp.example", "groups": ["mlflow-users"]}) is None
        assert not store.has_user("dave@corp.example")


class TestProvisioningBindsTheAccountItCreates:
    def test_a_created_user_is_bound_and_its_next_token_matches_on_the_identity(self, store, providers, monkeypatch):
        _enable_provisioning(monkeypatch)
        claims = {"sub": "partner-carol", "email": "carol@partner.example", "groups": ["mlflow-users"]}

        assert authenticate(PARTNER, claims) == "carol@partner.example"

        assert store.user_identity_repo.get_username_by_identity("partner", "partner-carol") == "carol@partner.example"
        # The default provider can no longer adopt it by name.
        assert authenticate(DEFAULT, {"sub": "corp-carol", "email": "carol@partner.example"}) is None


class TestDecisionsAreCached:
    def _lookups(self, store, claims, provider=PARTNER):
        real = store.user_identity_repo.get_username_by_identity
        with patch.object(store.user_identity_repo, "get_username_by_identity", side_effect=real) as lookup:
            authenticate(provider, claims)
        return lookup.call_count

    def test_a_repeated_token_costs_no_identity_lookup(self, store, providers):
        authenticate(PARTNER, {"sub": "partner-bob-sub", "email": BOB})
        assert self._lookups(store, {"sub": "partner-bob-sub", "email": BOB}) == 0

    def test_a_refusal_is_cached(self, store, providers):
        authenticate(PARTNER, {"sub": "partner-mallory", "email": ADMIN})
        assert self._lookups(store, {"sub": "partner-mallory", "email": ADMIN}) == 0

    def test_a_decision_to_create_is_not_cached(self, store, providers):
        """Until the account exists the name is free; the answer must follow the moment it is taken."""
        claims = {"sub": "partner-dave", "email": "dave@fresh.example"}
        authenticate(PARTNER, claims)
        assert self._lookups(store, claims) >= 1

    def test_a_failed_lookup_is_not_cached(self, store, providers, monkeypatch):
        claims = {"sub": "partner-bob-sub", "email": BOB}
        with patch.object(store.user_identity_repo, "get_username_by_identity", side_effect=RuntimeError("db down")):
            assert authenticate(PARTNER, claims) is None
        assert authenticate(PARTNER, claims) == BOB

    def test_binding_an_identity_drops_cached_decisions(self, store, providers):
        claims = {"sub": "corp-legacy-sub", "email": LEGACY}
        assert authenticate(DEFAULT, claims) == LEGACY  # adopted, and cached

        store.user_identity_repo.link("partner", "partner-legacy", LEGACY)

        assert authenticate(DEFAULT, claims) is None

    def test_deleting_a_user_drops_cached_decisions(self, store, providers):
        """Through the path the admin API and SCIM delete with. A user re-created under the name is
        somebody else, and a decision cached about the old account must not reach it."""
        from mlflow_oidc_auth.orphans import delete_user_reporting_orphans

        claims = {"sub": "partner-bob-sub", "email": BOB}
        assert authenticate(PARTNER, claims) == BOB  # cached

        delete_user_reporting_orphans(BOB, actor="admin", source="test", store=store)
        store.create_user(BOB, "Another Bob")  # not bound yet: nothing else flushes the cache

        assert authenticate(PARTNER, claims) is None


class TestAutomationKeepsWorking:
    """Automated tokens — a CI job's or a service principal's — reach the service account an
    administrator created for them, as the programmatic-access guide sets them up, from any provider."""

    def test_a_service_principal_reaches_its_admin_created_service_account(self, store, providers):
        store.create_user("ci-bot", "CI bot", is_service_account=True)

        assert authenticate(PARTNER, {"sub": "partner-client-ci", "preferred_username": "ci-bot"}) == "ci-bot"

    def test_a_kubernetes_service_account_is_its_cluster_providers_alone(self, store, providers):
        store.create_user("trainer.ml@serviceaccount.cluster.local", "ml/trainer", is_service_account=True, written_by="oidc:cluster")

        assert authenticate(PARTNER, {"sub": "partner-x", "email": "trainer.ml@serviceaccount.cluster.local"}) is None

    def test_an_admin_service_account_is_not_reachable_this_way(self, store, providers):
        store.create_user("root-bot", "Root bot", is_admin=True, is_service_account=True)

        assert authenticate(PARTNER, {"sub": "partner-x", "preferred_username": "root-bot"}) is None

    def test_a_service_account_bound_to_another_provider_is_refused(self, store, providers):
        store.create_user("bound-bot", "Bound bot", is_service_account=True)
        store.user_identity_repo.link("default", "corp-bound-bot", "bound-bot")

        assert authenticate(PARTNER, {"sub": "partner-x", "preferred_username": "bound-bot"}) is None

    def test_a_human_account_is_still_refused(self, store, providers):
        assert authenticate(PARTNER, {"sub": "partner-x", "email": LEGACY}) is None
