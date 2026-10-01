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


class TestServiceAccountsSignInOneWay:
    """A service account is internal — access tokens this plugin issues, never an IdP token — or
    external to one provider, whose tokens alone reach it, for the subject bound to it."""

    @pytest.fixture
    def through_middleware(self, store, providers, monkeypatch):
        """Requests through the real AuthMiddleware; a bearer token is validated as ``claims`` from ``provider``."""
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient

        app = FastAPI()

        @app.get("/api/2.0/mlflow/whoami")
        async def whoami(request: Request):
            return {"username": request.state.username}

        app.add_middleware(AuthMiddleware)
        client = TestClient(app)

        def call(provider=None, claims=None, basic=None):
            headers = {}
            if basic:
                from mlflow_oidc_auth.tests.scim.conftest import basic as basic_header

                headers = basic_header(*basic)
            else:
                headers = {"Authorization": "Bearer token"}
            with (
                patch.object(auth_middleware, "validate_token", return_value=claims or {}),
                patch.object(AuthMiddleware, "_provider_for", return_value=provider),
            ):
                response = client.get("/api/2.0/mlflow/whoami", headers=headers)
            return response.json().get("username") if response.status_code == 200 else None

        return call

    def test_an_internal_service_account_takes_no_idp_token(self, store, providers, through_middleware):
        store.create_user("ci-bot", "CI bot", is_service_account=True)

        assert through_middleware(PARTNER, {"sub": "partner-ci", "preferred_username": "ci-bot"}) is None
        assert through_middleware(DEFAULT, {"sub": "corp-ci", "preferred_username": "ci-bot"}) is None

    def test_an_internal_service_account_takes_its_issued_token(self, store, providers, through_middleware):
        from mlflow_oidc_auth.tests.token_helpers import set_known_token

        store.create_user("ci-bot", "CI bot", is_service_account=True)
        set_known_token(store, "ci-bot", "ci-bot-token")

        assert through_middleware(basic=("ci-bot", "ci-bot-token")) == "ci-bot"

    def test_a_single_provider_deployment_is_held_to_it_too(self, store, providers, through_middleware):
        providers(DEFAULT)
        store.create_user("ci-bot", "CI bot", is_service_account=True)

        assert through_middleware(DEFAULT, {"sub": "corp-ci", "preferred_username": "ci-bot"}) is None

    def test_an_external_service_account_binds_its_first_subject_and_takes_only_it(self, store, providers, through_middleware):
        store.create_user("ci-bot", "CI bot", is_service_account=True, service_account_source="partner")

        assert through_middleware(PARTNER, {"sub": "partner-ci", "preferred_username": "ci-bot"}) == "ci-bot"
        assert store.user_identity_repo.get_username_by_identity("partner", "partner-ci") == "ci-bot"
        assert through_middleware(PARTNER, {"sub": "partner-other", "preferred_username": "ci-bot"}) is None
        assert through_middleware(DEFAULT, {"sub": "corp-ci", "preferred_username": "ci-bot"}) is None

    def test_a_pre_bound_subject_is_the_only_one_accepted(self, store, providers, through_middleware):
        store.create_user("ci-bot", "CI bot", is_service_account=True, service_account_source="partner")
        store.user_identity_repo.link("partner", "repo:org/app:ref:refs/heads/main", "ci-bot", allow_additional_provider=True)

        assert through_middleware(PARTNER, {"sub": "repo:org/app:ref:refs/heads/main", "preferred_username": "ci-bot"}) == "ci-bot"
        assert through_middleware(PARTNER, {"sub": "repo:org/app:ref:refs/heads/dev", "preferred_username": "ci-bot"}) is None

    def test_an_external_service_account_takes_no_issued_token(self, store, providers, through_middleware):
        from mlflow_oidc_auth.tests.token_helpers import set_known_token

        store.create_user("ci-bot", "CI bot", is_service_account=True, service_account_source="partner")
        set_known_token(store, "ci-bot", "ci-bot-token")

        assert through_middleware(basic=("ci-bot", "ci-bot-token")) is None

    def test_a_person_is_not_judged_by_it(self, store, providers, through_middleware):
        assert through_middleware(PARTNER, {"sub": "partner-bob-sub", "email": BOB}) == BOB


def test_a_kubernetes_token_was_authorized_on_its_own_path():
    from mlflow_oidc_auth.entities.auth_context import AUTH_METHOD_WORKLOAD
    from mlflow_oidc_auth.middleware.auth_middleware import _KUBERNETES_BEARER, _service_account_denial

    cluster = _provider("cluster", type="k8s")
    other_cluster = _provider("cluster-b", type="k8s")

    assert _service_account_denial("t.ns@serviceaccount.cluster.local", True, "cluster", AUTH_METHOD_WORKLOAD, (_KUBERNETES_BEARER, cluster)) == ""
    assert _service_account_denial("t.ns@serviceaccount.cluster.local", True, "kubernetes", AUTH_METHOD_WORKLOAD, (_KUBERNETES_BEARER, cluster)) == ""
    # Another cluster allowing the same namespace, or an account re-pointed elsewhere, is refused.
    assert _service_account_denial("t.ns@serviceaccount.cluster.local", True, "cluster", AUTH_METHOD_WORKLOAD, (_KUBERNETES_BEARER, other_cluster))
    assert _service_account_denial("t.ns@serviceaccount.cluster.local", True, "partner", AUTH_METHOD_WORKLOAD, (_KUBERNETES_BEARER, cluster))


class TestAProviderThatAdoptsUnboundAccounts:
    """``bearer_adopts_unbound_accounts``: an account this provider's bearer provisioning created before
    identities were bound (unbound, not a service account) is reached and bound on first use."""

    ADOPTING = _provider("partner", bearer_adopts_unbound_accounts=True)

    def test_without_the_setting_such_an_account_is_refused(self, store, providers):
        store.create_user("ci-runner@partner.example", "CI runner")

        assert authenticate(PARTNER, {"sub": "partner-ci", "email": "ci-runner@partner.example"}) is None

    def test_with_it_the_account_is_reached_and_bound_to_the_token(self, store, providers):
        providers(DEFAULT, self.ADOPTING)
        store.create_user("ci-runner@partner.example", "CI runner")

        assert authenticate(self.ADOPTING, {"sub": "partner-ci", "email": "ci-runner@partner.example"}) == "ci-runner@partner.example"
        assert store.user_identity_repo.get_username_by_identity("partner", "partner-ci") == "ci-runner@partner.example"
        # Bound now: another subject asserting the same name is refused.
        assert authenticate(self.ADOPTING, {"sub": "partner-other", "email": "ci-runner@partner.example"}) is None

    def test_an_account_with_a_real_binding_or_an_admin_is_not_adopted(self, store, providers):
        providers(DEFAULT, self.ADOPTING)

        assert authenticate(self.ADOPTING, {"sub": "partner-x", "email": ADMIN}) is None  # bound to default, and an admin
        assert authenticate(self.ADOPTING, {"sub": "partner-y", "email": BOB}) is None  # bound to partner's other subject


class TestAnAdministratorUnbindsAnIdentity:
    """A subject that changed (a re-created client, a workflow moved to an environment) locks its
    account out; an administrator removes the old binding so the new subject can be bound."""

    @pytest.fixture
    def users_api(self, store, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import mlflow_oidc_auth.dependencies as dependencies
        import mlflow_oidc_auth.routers.users as users_router

        caller = {"username": "root@corp.example", "admin": True}

        async def username(request=None):
            return caller["username"]

        async def is_admin(request=None):
            return caller["admin"]

        monkeypatch.setattr(dependencies, "get_username", username)
        monkeypatch.setattr(dependencies, "get_is_admin", is_admin)
        app = FastAPI()
        app.include_router(users_router.users_router)
        with TestClient(app) as client:
            client.caller = caller
            yield client

    def test_listing_and_unbinding_lets_a_new_subject_bind_on_adoption(self, store, providers, users_api):
        adopting = _provider("partner", bearer_adopts_unbound_accounts=True)
        providers(DEFAULT, adopting)
        github = "repo:org/app:ref:refs/heads/main"

        response = users_api.get(f"/api/2.0/mlflow/users/{BOB}/identities")
        assert response.json() == [{"provider_id": "partner", "subject": "partner-bob-sub"}]
        response = users_api.delete(f"/api/2.0/mlflow/users/{BOB}/identities", params={"provider_id": "partner", "subject": "partner-bob-sub"})
        assert response.status_code == 200, response.text

        assert authenticate(adopting, {"sub": github, "email": BOB}) == BOB
        assert store.user_identity_repo.get_username_by_identity("partner", github) == BOB

    def test_an_unknown_binding_is_404(self, store, providers, users_api):
        response = users_api.delete(f"/api/2.0/mlflow/users/{BOB}/identities", params={"provider_id": "partner", "subject": "nope"})

        assert response.status_code == 404

    def test_a_non_admin_can_do_neither(self, store, providers, users_api):
        users_api.caller.update(username=BOB, admin=False)

        response = users_api.get(f"/api/2.0/mlflow/users/{BOB}/identities")
        assert response.status_code == 403
        response = users_api.delete(f"/api/2.0/mlflow/users/{BOB}/identities", params={"provider_id": "partner", "subject": "partner-bob-sub"})
        assert response.status_code == 403
        assert store.user_identity_repo.get_username_by_identity("partner", "partner-bob-sub") == BOB


@pytest.fixture
def admin_api(store, monkeypatch):
    """The users router as an administrator."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import mlflow_oidc_auth.dependencies as dependencies
    import mlflow_oidc_auth.routers.users as users_router

    async def username(request=None):
        return "root@corp.example"

    async def is_admin(request=None):
        return True

    monkeypatch.setattr(dependencies, "get_username", username)
    monkeypatch.setattr(dependencies, "get_is_admin", is_admin)
    app = FastAPI()
    app.include_router(users_router.users_router)
    app.dependency_overrides[dependencies.require_interactive_login] = lambda: None  # an admin's browser session
    from mlflow_oidc_auth import utils

    app.dependency_overrides[utils.get_username] = lambda: "root@corp.example"
    app.dependency_overrides[utils.get_is_admin] = lambda: True
    with TestClient(app) as client:
        yield client


USERS = "/api/2.0/mlflow/users"


class TestManagingAServiceAccountsSource:
    def test_the_sources_are_internal_and_each_oidc_provider(self, store, providers, admin_api):
        assert [s["id"] for s in admin_api.get(f"{USERS}/service-account-sources").json()] == ["internal", "default", "partner"]

    def test_a_service_account_is_internal_unless_told_otherwise(self, store, providers, admin_api):
        response = admin_api.post(USERS, json={"username": "ci-bot", "display_name": "CI", "is_service_account": True})
        assert response.status_code == 201, response.text

        assert store.get_user_profile("ci-bot").service_account_source == "internal"

    def test_creating_an_external_one_binds_the_given_subject(self, store, providers, admin_api):
        response = admin_api.post(
            USERS,
            json={"username": "ci-bot", "display_name": "CI", "is_service_account": True, "service_account_source": "partner", "subject": "repo:o/a:ref:main"},
        )
        assert response.status_code == 201, response.text

        assert store.get_user_profile("ci-bot").service_account_source == "partner"
        assert store.user_identity_repo.list_identities_for_username("ci-bot") == [("partner", "repo:o/a:ref:main")]

    @pytest.mark.parametrize(
        "body",
        [
            {"username": "x", "display_name": "X", "is_service_account": True, "service_account_source": "nope"},
            {"username": "x", "display_name": "X", "is_service_account": True, "service_account_source": "internal", "subject": "s"},
            {"username": "x", "display_name": "X", "service_account_source": "partner"},
        ],
    )
    def test_bad_requests_are_refused(self, store, providers, admin_api, body):
        assert admin_api.post(USERS, json=body).status_code == 400
        assert not store.has_user("x")

    def test_going_external_revokes_issued_tokens_and_none_can_be_issued(self, store, providers, admin_api):
        from mlflow_oidc_auth.tests.token_helpers import set_known_token

        store.create_user("ci-bot", "CI", is_service_account=True)
        set_known_token(store, "ci-bot", "ci-bot-token")

        response = admin_api.put(f"{USERS}/ci-bot/service-account-source", json={"source": "partner"})
        assert response.status_code == 200, response.text

        assert store.list_user_tokens("ci-bot") == []
        from datetime import datetime, timedelta, timezone

        expiration = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        issue = admin_api.post(f"{USERS}/ci-bot/tokens", json={"name": "t", "expiration": expiration})
        assert issue.status_code == 409, issue.text

    def test_going_internal_unbinds_identities(self, store, providers, admin_api):
        store.create_user("ci-bot", "CI", is_service_account=True, service_account_source="partner")
        store.user_identity_repo.link("partner", "s1", "ci-bot", allow_additional_provider=True)

        assert admin_api.put(f"{USERS}/ci-bot/service-account-source", json={"source": "internal"}).status_code == 200

        assert store.user_identity_repo.list_identities_for_username("ci-bot") == []

    def test_a_person_has_no_source(self, store, providers, admin_api):
        assert admin_api.put(f"{USERS}/{BOB}/service-account-source", json={"source": "internal"}).status_code == 409


class TestReviewFollowUps:
    def test_no_access_token_can_be_minted_for_an_external_account_by_any_route(self, store, providers, admin_api):
        store.create_user("ci-bot", "CI", is_service_account=True, service_account_source="partner")

        response = admin_api.patch(f"{USERS}/access-token", json={"username": "ci-bot"})

        assert response.status_code == 409, response.text
        assert store.list_user_tokens("ci-bot") == []

    def test_any_change_of_source_revokes_issued_tokens(self, store, providers, admin_api):
        from mlflow_oidc_auth.tests.token_helpers import set_known_token

        store.create_user("ci-bot", "CI", is_service_account=True, service_account_source="partner")
        set_known_token(store, "ci-bot", "minted-while-external")  # e.g. from before this release

        assert admin_api.put(f"{USERS}/ci-bot/service-account-source", json={"source": "internal"}).status_code == 200

        assert store.list_user_tokens("ci-bot") == []

    def test_an_external_admin_account_needs_its_subject_now(self, store, providers, admin_api):
        body = {"username": "root-bot", "display_name": "R", "is_service_account": True, "is_admin": True, "service_account_source": "partner"}

        assert admin_api.post(USERS, json=body).status_code == 400
        assert admin_api.post(USERS, json={**body, "subject": "client-root"}).status_code == 201

    def test_a_first_token_never_binds_an_admin_account(self, store, providers):
        from mlflow_oidc_auth.entities.auth_context import AUTH_METHOD_BEARER
        from mlflow_oidc_auth.middleware.auth_middleware import _service_account_denial

        store.create_user("root-bot", "R", is_admin=True, is_service_account=True, service_account_source="partner")

        assert _service_account_denial("root-bot", True, "partner", AUTH_METHOD_BEARER, (PARTNER, "attacker"), is_admin=True)
        assert store.user_identity_repo.list_identities_for_username("root-bot") == []

    def test_racing_first_tokens_leave_only_the_earliest_binding(self, store, providers, monkeypatch):
        from mlflow_oidc_auth.entities.auth_context import AUTH_METHOD_BEARER
        from mlflow_oidc_auth.middleware.auth_middleware import _service_account_denial

        store.create_user("ci-bot", "CI", is_service_account=True, service_account_source="partner")
        store.user_identity_repo.link("partner", "winner", "ci-bot", allow_additional_provider=True)  # bound meanwhile
        real = store.user_identity_repo.list_identities_for_username
        calls = {"n": 0}

        def listing(username):
            calls["n"] += 1
            return [] if calls["n"] == 1 else real(username)  # the loser read before the winner's insert

        monkeypatch.setattr(store.user_identity_repo, "list_identities_for_username", listing)

        assert _service_account_denial("ci-bot", True, "partner", AUTH_METHOD_BEARER, (PARTNER, "loser"))
        assert real("ci-bot") == [("partner", "winner")]

    def test_a_refused_subject_changes_nothing(self, store, providers, admin_api):
        store.create_user("ci-bot", "CI", is_service_account=True)

        response = admin_api.put(f"{USERS}/ci-bot/service-account-source", json={"source": "partner", "subject": "partner-bob-sub"})

        assert response.status_code == 409, response.text
        assert store.get_user_profile("ci-bot").service_account_source == "internal"

    def test_an_existing_username_is_not_re_pointed_by_create(self, store, providers, admin_api):
        store.create_user("ci-bot", "CI", is_service_account=True)

        body = {"username": "ci-bot", "display_name": "CI", "is_service_account": True, "service_account_source": "partner"}
        assert admin_api.post(USERS, json=body).status_code == 409
        assert store.get_user_profile("ci-bot").service_account_source == "internal"

    def test_a_kubernetes_token_is_refused_once_its_account_is_internal(self):
        from mlflow_oidc_auth.entities.auth_context import AUTH_METHOD_WORKLOAD
        from mlflow_oidc_auth.middleware.auth_middleware import _KUBERNETES_BEARER, _service_account_denial

        assert _service_account_denial(
            "t.ns@serviceaccount.cluster.local", True, "internal", AUTH_METHOD_WORKLOAD, (_KUBERNETES_BEARER, _provider("cluster", type="k8s"))
        )

    def test_a_service_accounts_session_is_flagged_by_the_session_lookup(self, store):
        from datetime import datetime, timedelta, timezone

        store.create_user("ci-bot", "CI", is_service_account=True)
        session_id = store.create_auth_session("ci-bot", datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1))

        assert store.auth_session_repo.resolve(session_id).is_service_account is True

    def test_a_subject_that_cannot_be_bound_on_create_leaves_no_account(self, store, providers, admin_api, monkeypatch):
        from mlflow.exceptions import MlflowException

        monkeypatch.setattr(store.user_identity_repo, "link", lambda *a, **k: (_ for _ in ()).throw(MlflowException("bound meanwhile")))
        body = {"username": "ci-bot", "display_name": "CI", "is_service_account": True, "service_account_source": "partner", "subject": "s1"}

        assert admin_api.post(USERS, json=body).status_code == 409
        assert not store.has_user("ci-bot")

    def test_a_binding_that_cannot_be_checked_is_a_denial(self, store, providers, monkeypatch):
        from mlflow_oidc_auth.entities.auth_context import AUTH_METHOD_BEARER
        from mlflow_oidc_auth.middleware.auth_middleware import _service_account_denial

        store.create_user("ci-bot", "CI", is_service_account=True, service_account_source="partner")
        monkeypatch.setattr(store.user_identity_repo, "list_identities_for_username", lambda *_: (_ for _ in ()).throw(RuntimeError("db down")))

        assert _service_account_denial("ci-bot", True, "partner", AUTH_METHOD_BEARER, (PARTNER, "s1")) != ""


def test_a_kubernetes_account_an_older_replica_created_keeps_working():
    """During a rolling upgrade an older replica creates Kubernetes accounts with no source recorded."""
    from mlflow_oidc_auth.entities.auth_context import AUTH_METHOD_WORKLOAD
    from mlflow_oidc_auth.middleware.auth_middleware import _KUBERNETES_BEARER, _service_account_denial

    cluster = _provider("cluster", type="k8s")
    assert _service_account_denial("t.ns@serviceaccount.cluster.local", True, None, AUTH_METHOD_WORKLOAD, (_KUBERNETES_BEARER, cluster)) == ""


class TestOnlyAdministratorsManageServiceAccountSources:
    @pytest.fixture
    def member_api(self, store, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import mlflow_oidc_auth.dependencies as dependencies
        import mlflow_oidc_auth.routers.users as users_router

        async def username(request=None):
            return BOB

        async def is_admin(request=None):
            return False

        monkeypatch.setattr(dependencies, "get_username", username)
        monkeypatch.setattr(dependencies, "get_is_admin", is_admin)
        app = FastAPI()
        app.include_router(users_router.users_router)
        with TestClient(app) as client:
            yield client

    def test_a_member_can_neither_list_nor_change_sources_nor_create_with_one(self, store, providers, member_api):
        store.create_user("ci-bot", "CI", is_service_account=True)

        response = member_api.get(f"{USERS}/service-account-sources")
        assert response.status_code == 403
        response = member_api.put(f"{USERS}/ci-bot/service-account-source", json={"source": "partner"})
        assert response.status_code == 403
        body = {"username": "x-bot", "display_name": "X", "is_service_account": True, "service_account_source": "partner"}
        response = member_api.post(USERS, json=body)
        assert response.status_code == 403
        assert store.get_user_profile("ci-bot").service_account_source == "internal"
        assert not store.has_user("x-bot")


class TestFinalReviewFollowUps:
    ADOPTING = _provider("partner", bearer_adopts_unbound_accounts=True)

    def test_adoption_never_reaches_into_another_providers_domain(self, store, providers):
        providers(DEFAULT, self.ADOPTING)  # LEGACY is unbound, in corp.example where ADMIN is default's

        assert authenticate(self.ADOPTING, {"sub": "partner-mallory", "email": LEGACY}) is None
        assert store.user_identity_repo.list_identities_for_username(LEGACY) == []

    def test_adoption_never_takes_an_account_from_before_identities_were_recorded(self, store, providers):
        providers(DEFAULT, self.ADOPTING)
        store.create_user("old-ci@partner.example", "Old CI")
        store.user_identity_repo.link("default", "old-ci@partner.example", "old-ci@partner.example")  # the placeholder

        assert authenticate(self.ADOPTING, {"sub": "partner-ci", "email": "old-ci@partner.example"}) is None

    def test_a_pre_identity_service_account_pointed_at_default_binds_its_first_token(self, store, providers, admin_api):
        providers(DEFAULT)
        store.create_user("ci-bot", "CI", is_service_account=True)
        store.user_identity_repo.link("default", "ci-bot", "ci-bot")  # the placeholder

        assert admin_api.put(f"{USERS}/ci-bot/service-account-source", json={"source": "default"}).status_code == 200

        from mlflow_oidc_auth.entities.auth_context import AUTH_METHOD_BEARER
        from mlflow_oidc_auth.middleware.auth_middleware import _service_account_denial

        assert _service_account_denial("ci-bot", True, "default", AUTH_METHOD_BEARER, (DEFAULT, "corp-client-ci")) == ""

    def test_an_unidentified_provider_is_a_denial_not_an_error(self, store):
        from mlflow_oidc_auth.entities.auth_context import AUTH_METHOD_BEARER
        from mlflow_oidc_auth.middleware.auth_middleware import _service_account_denial

        assert _service_account_denial("ci-bot", True, "partner", AUTH_METHOD_BEARER, (None, "s"))

    def test_promoting_an_external_service_account_drops_its_first_token_subject(self, store, providers):
        store.create_user("etl", "ETL", is_service_account=True, service_account_source="partner")
        store.user_identity_repo.link("partner", "first-token-sub", "etl", allow_additional_provider=True)

        store.update_user("etl", is_admin=True)

        assert store.user_identity_repo.list_identities_for_username("etl") == []


@pytest.mark.parametrize("provider_id", ["internal", "kubernetes"])
def test_reserved_provider_ids_are_refused(provider_id):
    from mlflow_oidc_auth.tests.test_provider_registry import build, valid_entry

    result = build([valid_entry(id=provider_id)])

    assert result.providers == []
    assert any("is reserved" in error for error in result.errors)
