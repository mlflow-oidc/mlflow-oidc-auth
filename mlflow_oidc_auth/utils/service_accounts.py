"""How a service account signs in.

``users.service_account_source`` holds, for a service account:

* :data:`INTERNAL_SOURCE` — it signs in only with access tokens this plugin issues for it; no
  identity provider's token reaches it, whatever username the token claims;
* a provider id — it signs in only with that provider's tokens, for the subject bound to it (the
  first token binds one when none is). Its lifecycle lives in the IdP, so access tokens this plugin
  issued do not work for it, and none can be issued.

A Kubernetes service account is created for, and recorded as, its cluster provider; its tokens are
authorized on their own path. The check itself runs on every authenticated request in
``middleware/auth_middleware._service_account_denial``, from the profile row already fetched there.
"""

INTERNAL_SOURCE = "internal"

#: Recorded by the migration on Kubernetes service accounts created before sources existed.
KUBERNETES_SOURCE = "kubernetes"


def is_external(source) -> bool:
    """Whether a service account with this source signs in through an identity provider."""
    return bool(source) and source != INTERNAL_SOURCE


def selectable_sources() -> list:
    """The sources an administrator may give a service account: internal, and each OIDC provider.

    A Kubernetes provider's service accounts are created by that provider itself, and a SAML
    provider has no bearer tokens, so neither is offered.

    Returns:
        ``[{"id", "display_name", "type"}]``, internal first.
    """
    from mlflow_oidc_auth.config import config

    sources = [{"id": INTERNAL_SOURCE, "display_name": "Internal (issued access tokens only)", "type": "internal"}]
    for provider in config.AUTH_PROVIDERS.providers:
        # ``kubernetes`` is reserved for the migration's Kubernetes accounts.
        if provider.type == "oidc" and provider.id != KUBERNETES_SOURCE:
            sources.append({"id": provider.id, "display_name": provider.display_name or provider.id, "type": provider.type})
    return sources


def validate_source(source: str, subject, *, is_admin: bool = False) -> str:
    """Normalise and check a source (and subject) an administrator asked for.

    An external administrator account must be bound to its subject now: left to the provider's
    first token, whoever can mint a token naming it first would hold administrator rights.

    Returns:
        The source.

    Raises:
        ValueError: An unknown source, a subject for an internal account, or an external
            administrator account without one.
    """
    source = (source or "").strip()
    if source not in {entry["id"] for entry in selectable_sources()}:
        raise ValueError(f"unknown service account source {source!r}: 'internal' or the id of an OIDC provider")
    if source == INTERNAL_SOURCE and subject:
        raise ValueError("an internal service account has no provider subject")
    if is_external(source) and is_admin and not (subject or "").strip():
        raise ValueError("an external administrator service account needs its subject bound now")
    return source


def apply_source(username: str, source: str, subject=None) -> None:
    """Make service account ``username`` sign in through ``source``.

    Becoming external revokes the access tokens issued for it (its lifecycle moves to the IdP) and
    unbinds identities of other providers; becoming internal unbinds every identity. A given subject
    is bound now; otherwise an external account binds its provider's first token.

    Raises:
        ValueError: As :func:`validate_source`.
        MlflowException: An unknown user or one that is not a service account.
    """
    from mlflow.exceptions import MlflowException
    from mlflow.protos.databricks_pb2 import RESOURCE_ALREADY_EXISTS

    from mlflow_oidc_auth.store import store
    from mlflow_oidc_auth.utils.bearer_identity_cache import flush_bearer_identity_cache

    profile = store.get_user_profile(username)
    source = validate_source(source, subject, is_admin=profile.is_admin is True)
    subject = (subject or "").strip()
    # Everything that can refuse is checked before anything changes.
    if subject and store.user_identity_repo.get_username_by_identity(source, subject) not in (None, profile.username):
        raise MlflowException("That subject is already bound to another account", RESOURCE_ALREADY_EXISTS)
    changed = (profile.service_account_source or INTERNAL_SOURCE) != source
    store.set_service_account_source(username, source)
    for provider_id, bound in store.user_identity_repo.list_identities_for_username(username):
        placeholder = provider_id == "default" and bound == profile.username
        if placeholder or source == INTERNAL_SOURCE or provider_id != source or (subject and bound != subject):
            store.user_identity_repo.unlink(provider_id, bound, username)
    if changed:
        # Credentials of the old way stop working: issued tokens (an external account keeps none;
        # one made internal starts from tokens issued from now on) and browser sessions.
        store.delete_user_tokens(username)
        store.revoke_all_auth_sessions(username)
    if is_external(source) and subject:
        store.user_identity_repo.link(source, subject, username, allow_additional_provider=True)
    flush_bearer_identity_cache()
