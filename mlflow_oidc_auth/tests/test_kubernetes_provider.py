"""Kubernetes service-account tokens as a bearer credential (issue #314).

A projected token is an ordinary JWT that #313 already validates; what is new is everything
around it — where a cluster's keys come from, what ``sub`` means, and who may become a user on
the strength of it.

The last question is the one that matters most. An OIDC bearer token is gated on a groups claim,
so a token from a stranger's account provisions nothing. A service-account token has no groups
claim at all, so if that gate is simply skipped, **every pod in the cluster** that can read its
own projected token becomes an MLflow user. The namespace allowlist is the whole decision, and
these cases pin it.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mlflow_oidc_auth.kubernetes import (
    ServiceAccount,
    ServiceAccountError,
    load_inline_jwks,
    namespace_is_allowed,
    parse_service_account,
)
from mlflow_oidc_auth.middleware.auth_middleware import AuthMiddleware


class TestParsingTheSubject:
    def test_a_projected_token_subject_parses(self):
        account = parse_service_account("system:serviceaccount:team-a:trainer")

        assert account == ServiceAccount(namespace="team-a", name="trainer")

    def test_the_username_is_readable_and_unmistakable(self):
        """It ends up in the admin UI and on permission grants, so
        ``system:serviceaccount:team-a:trainer`` is not usable as-is."""
        account = parse_service_account("system:serviceaccount:team-a:trainer")

        assert account.username == "trainer.team-a@serviceaccount.cluster.local"
        assert account.group == "k8s:team-a"

    def test_two_namespaces_cannot_render_the_same_username(self):
        """``-`` is legal *inside* a DNS label, so ``{namespace}-{name}`` is ambiguous:
        ``prod-etl``/``writer`` and ``prod``/``etl-writer`` collide.

        That is not cosmetic. Anyone able to create a service account in one allowlisted
        namespace could pick a name that renders as an account in another, and — since the
        username is the identity key — inherit its permissions. ``.`` cannot appear in a label,
        so the halves stay distinguishable.
        """
        first = parse_service_account("system:serviceaccount:prod-etl:writer")
        second = parse_service_account("system:serviceaccount:prod:etl-writer")

        assert first.username != second.username
        assert first.group != second.group

    @pytest.mark.parametrize(
        "subject",
        [
            "system:serviceaccount:team-a",
            "system:serviceaccount::trainer",
            "system:serviceaccount:team-a:",
            "system:serviceaccount:team-a:trainer:extra",
            "serviceaccount:team-a:trainer",
            "system:node:worker-1",
            "alice@example.com",
            "",
        ],
    )
    def test_anything_that_is_not_a_service_account_subject_is_refused(self, subject):
        with pytest.raises(ServiceAccountError):
            parse_service_account(subject)

    @pytest.mark.parametrize("subject", [None, 42, ["system:serviceaccount:a:b"], {"sub": "x"}])
    def test_a_non_string_subject_is_refused(self, subject):
        with pytest.raises(ServiceAccountError):
            parse_service_account(subject)

    @pytest.mark.parametrize(
        "namespace",
        ["Team-A", "team_a", "team a", "team/a", "team.a", "-team", "team-", "a" * 64, "team@a", "../etc"],
    )
    def test_a_namespace_outside_the_kubernetes_character_set_is_refused(self, namespace):
        """The claim is signed, so a healthy cluster cannot assert this — but the value becomes a
        username and a group name, and a hostile or compromised cluster configured as a provider
        should not get to choose what those contain."""
        with pytest.raises(ServiceAccountError):
            parse_service_account(f"system:serviceaccount:{namespace}:trainer")

    def test_a_name_outside_the_character_set_is_refused(self):
        with pytest.raises(ServiceAccountError):
            parse_service_account("system:serviceaccount:team-a:Trainer_1")


class TestTheNamespaceAllowlist:
    def test_a_listed_namespace_is_allowed(self):
        assert namespace_is_allowed("team-a", ("team-a", "team-b")) is True

    def test_an_unlisted_namespace_is_not(self):
        assert namespace_is_allowed("kube-system", ("team-a",)) is False

    def test_an_empty_allowlist_means_nobody(self):
        """Not "everybody". With no groups claim to narrow on, a permissive empty list would make
        every pod in the cluster an MLflow user the moment the provider was configured."""
        assert namespace_is_allowed("team-a", ()) is False


class TestInlineKeys:
    """The mode that needs no network: the operator pastes the cluster's JWKS into config."""

    def test_a_jwks_object_is_accepted(self):
        jwks = {"keys": [{"kty": "RSA", "kid": "abc"}]}

        assert load_inline_jwks(jwks) == jwks

    def test_a_json_string_is_accepted(self):
        jwks = {"keys": [{"kty": "RSA", "kid": "abc"}]}

        assert load_inline_jwks(json.dumps(jwks)) == jwks

    @pytest.mark.parametrize("bad", ["not json", "[]", '{"keys": []}', '{"keys": "abc"}', "{}", '{"kid": "abc"}'])
    def test_anything_that_is_not_a_key_set_is_refused(self, bad):
        with pytest.raises(ValueError):
            load_inline_jwks(bad)


class TestProvisioningAServiceAccount:
    """The gate an OIDC token passes through does not exist for this one."""

    @staticmethod
    def _provider(**overrides):
        fields = {
            "id": "cluster",
            "type": "k8s",
            "audience": "mlflow-api",
            "issuer": "https://kubernetes.default.svc",
            "namespace_allowlist": ("team-a",),
        }
        fields.update(overrides)
        return SimpleNamespace(**fields)

    def _provision(self, payload, provider):
        """Drive the real authentication path, so what is asserted is what a request does."""
        with (
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.user.populate_groups") as populate_groups,
            patch("mlflow_oidc_auth.user.update_user") as update_user,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
        ):
            cfg.OIDC_PROVISION_ON_BEARER_AUTH = True
            store.has_user.return_value = False
            self.outcome = AuthMiddleware(app=MagicMock())._authenticate_service_account("tok", payload, provider)
            return create_user, populate_groups, update_user

    def test_a_listed_namespace_is_provisioned_as_a_service_account(self):
        payload = {"sub": "system:serviceaccount:team-a:trainer"}

        create_user, populate_groups, update_user = self._provision(payload, self._provider())

        assert self.outcome == (True, "trainer.team-a@serviceaccount.cluster.local", "")
        create_user.assert_called_once()
        assert create_user.call_args.kwargs["username"] == "trainer.team-a@serviceaccount.cluster.local"
        assert create_user.call_args.kwargs["is_service_account"] is True
        assert create_user.call_args.kwargs["is_admin"] is False
        populate_groups.assert_called_once_with(group_names=["k8s:team-a"])

    def test_the_oidc_provisioning_flag_is_not_a_hidden_prerequisite(self):
        """OIDC_PROVISION_ON_BEARER_AUTH gates provisioning from an *OIDC* token, where the
        alternative is trusting whatever groups an arbitrary corporate token carries.

        Here the opt-in already exists and is narrower — a provider the operator configured and a
        namespace they named in its allowlist. Requiring the OIDC flag as well would mean the
        documented setup authenticates the token and then returns 401 as an unknown user, with
        nothing pointing at why.
        """
        payload = {"sub": "system:serviceaccount:team-a:trainer"}

        with (
            patch("mlflow_oidc_auth.user.create_user") as create_user,
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
        ):
            cfg.OIDC_PROVISION_ON_BEARER_AUTH = False
            store.has_user.return_value = False
            allowed, username, _ = AuthMiddleware(app=MagicMock())._authenticate_service_account("tok", payload, self._provider())

        assert allowed is True
        create_user.assert_called_once()

    def test_an_unlisted_namespace_is_refused_outright(self):
        """Not merely "not provisioned": the request does not authenticate at all, so an account
        that was provisioned before the namespace was removed from the list loses access too."""
        payload = {"sub": "system:serviceaccount:kube-system:default"}

        create_user, _, _ = self._provision(payload, self._provider())

        assert self.outcome[0] is False
        create_user.assert_not_called()

    def test_removing_a_namespace_revokes_an_existing_account(self):
        """The allowlist is re-read on every request, so offboarding a team by editing it works.

        Checked only at provisioning, it would revoke nothing: every service account that had
        authenticated once would keep its user row, its group and its permissions while kubelet
        went on renewing its token.
        """
        payload = {"sub": "system:serviceaccount:team-b:trainer"}

        with (
            patch("mlflow_oidc_auth.user.create_user"),
            patch("mlflow_oidc_auth.middleware.auth_middleware.store") as store,
            patch("mlflow_oidc_auth.middleware.auth_middleware.config") as cfg,
        ):
            cfg.OIDC_PROVISION_ON_BEARER_AUTH = True
            store.has_user.return_value = True  # it authenticated before team-b was removed
            allowed, username, _ = AuthMiddleware(app=MagicMock())._authenticate_service_account("tok", payload, self._provider())

        assert allowed is False

    def test_an_empty_allowlist_admits_nobody(self):
        payload = {"sub": "system:serviceaccount:team-a:trainer"}

        create_user, _, _ = self._provision(payload, self._provider(namespace_allowlist=()))

        assert self.outcome[0] is False
        create_user.assert_not_called()

    def test_a_malformed_subject_does_not_authenticate(self):
        create_user, _, _ = self._provision({"sub": "alice@example.com"}, self._provider())

        assert self.outcome[0] is False
        create_user.assert_not_called()

    def test_a_missing_subject_does_not_authenticate(self):
        create_user, _, _ = self._provision({}, self._provider())

        assert self.outcome[0] is False
        create_user.assert_not_called()

    def test_a_service_account_is_never_an_admin(self):
        """No claim a cluster can assert should confer administrator rights here, and
        OIDC_TRUST_BEARER_GROUP_CLAIMS deliberately does not reach this path: it opts into
        trusting a directory's group names, which is a different statement from trusting a
        namespace."""
        payload = {"sub": "system:serviceaccount:team-a:trainer", "groups": ["mlflow-admins"], "is_admin": True}

        create_user, _, _ = self._provision(payload, self._provider())

        assert create_user.call_args.kwargs["is_admin"] is False

    def test_a_refusal_is_audited(self):
        events = []
        payload = {"sub": "system:serviceaccount:kube-system:default"}

        import mlflow_oidc_auth.middleware.auth_middleware as middleware_module

        middleware_module._denial_audit_seen.clear()
        with patch("mlflow_oidc_auth.middleware.auth_middleware.emit_audit_event", lambda event, **kw: events.append((event, kw))):
            self._provision(payload, self._provider())

        assert [event for event, _ in events] == ["auth.denied_namespace"]
        assert events[0][1]["status"] == "denied"
        assert events[0][1]["detail"]["namespace"] == "kube-system"


class TestTheRegistryRefusesAnUnusableClusterProvider:
    """Both requirements are the difference between a provider and an open door, so each is
    refused at load with an error that says why."""

    @staticmethod
    def _build(entry):
        from types import SimpleNamespace as NS

        from mlflow_oidc_auth.provider_registry import build_provider_registry

        class Manager:
            @staticmethod
            def get(key, default=None):
                return json.dumps([entry]) if key == "AUTH_PROVIDERS" else default

        app_config = NS(
            OIDC_PROVIDER_DISPLAY_NAME="Login with OIDC",
            OIDC_AUDIENCE=None,
            OIDC_ISSUER=None,
            OIDC_DISCOVERY_URL="https://idp.example.com/.well-known/openid-configuration",
            OIDC_CLIENT_ID="client",
        )
        return build_provider_registry(Manager(), app_config)

    @staticmethod
    def _entry(**overrides):
        entry = {
            "id": "cluster",
            "type": "k8s",
            "audience": "mlflow-api",
            "issuer": "https://kubernetes.default.svc",
            "namespace_allowlist": ["team-a"],
            "jwks_uri": "https://kubernetes.default.svc/openid/v1/jwks",
        }
        entry.update(overrides)
        return entry

    def test_a_complete_entry_is_accepted(self):
        result = self._build(self._entry())

        assert [provider.id for provider in result.providers] == ["cluster"]
        assert result.providers[0].namespace_allowlist == ("team-a",)

    def test_no_namespace_allowlist_is_refused(self):
        entry = self._entry()
        entry.pop("namespace_allowlist")

        result = self._build(entry)

        assert result.providers == []
        assert any("namespace_allowlist" in error for error in result.errors)

    def test_an_empty_namespace_allowlist_is_refused(self):
        result = self._build(self._entry(namespace_allowlist=[]))

        assert result.providers == []

    @pytest.mark.parametrize("namespace", ["Team-A", "team_a", "system:serviceaccount:team-a", "team a", "a" * 64])
    def test_an_allowlist_entry_that_could_never_match_is_refused(self, namespace):
        """Worse than a rejected entry: it passes validation and then silently denies every pod
        in the namespace the operator meant to allow."""
        result = self._build(self._entry(namespace_allowlist=[namespace]))

        assert result.providers == []
        assert any("never match" in error for error in result.errors)

    def test_a_real_namespace_is_accepted(self):
        result = self._build(self._entry(namespace_allowlist=["team-a", "kube-system", "ml-1"]))

        assert result.providers[0].namespace_allowlist == ("team-a", "kube-system", "ml-1")

    def test_no_key_source_at_all_is_refused(self):
        entry = self._entry()
        entry.pop("jwks_uri")

        result = self._build(entry)

        assert result.providers == []
        assert any("key source" in error for error in result.errors)

    def test_a_malformed_inline_key_set_is_refused(self):
        entry = self._entry(jwks_inline="{not json")
        entry.pop("jwks_uri")

        result = self._build(entry)

        assert result.providers == []
        assert any("JWKS" in error for error in result.errors)

    def test_in_cluster_alone_is_a_key_source(self):
        entry = self._entry(in_cluster=True)
        entry.pop("jwks_uri")

        result = self._build(entry)

        assert [provider.id for provider in result.providers] == ["cluster"]

    def test_an_unpinned_audience_is_refused(self):
        """Inherited from the shared rules, and it matters most here: an unpinned audience
        accepts any pod's token minted for any service."""
        entry = self._entry()
        entry.pop("audience")

        result = self._build(entry)

        assert result.providers == []
