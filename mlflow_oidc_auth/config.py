"""
Application configuration for MLflow OIDC Auth Plugin.

This module provides configuration management with support for multiple
configuration sources (environment variables, AWS Secrets Manager, Azure Key Vault,
Kubernetes Secrets, etc.) through the pluggable provider system.

Environment Variables for Provider Configuration:
    CONFIG_AWS_SECRETS_ENABLED: Enable AWS Secrets Manager provider
    CONFIG_AWS_PARAMETER_STORE_ENABLED: Enable AWS Parameter Store provider
    CONFIG_AZURE_KEYVAULT_ENABLED: Enable Azure Key Vault provider
    CONFIG_VAULT_ENABLED: Enable HashiCorp Vault provider
    CONFIG_K8S_SECRETS_ENABLED: Enable Kubernetes Secrets provider
    CONFIG_PROVIDERS: Comma-separated list of providers to use (optional filter)

See config_providers/ for detailed configuration of each provider.
"""

import secrets

from dotenv import load_dotenv

from mlflow_oidc_auth.config_providers import config_manager
from mlflow_oidc_auth.logger import get_logger

load_dotenv()  # take environment variables from .env.
logger = get_logger()


def get_bool_env_variable(variable: str, default_value: bool) -> bool:
    """Get a boolean value from configuration.

    Parameters:
        variable: The configuration key name.
        default_value: Default value if not found.

    Returns:
        Boolean value parsed from configuration.
    """
    return config_manager.get_bool(variable, default=default_value)


class AppConfig:
    """Application configuration container.

    This class loads configuration from the pluggable provider system,
    which supports multiple sources in priority order:
        1. Cloud providers (AWS Secrets Manager, Azure Key Vault, etc.)
        2. Kubernetes Secrets (mounted as files)
        3. Environment variables (fallback)

    Attributes:
        DEFAULT_MLFLOW_PERMISSION: Default permission level for new resources.
        SECRET_KEY: Secret key for session management.
        OIDC_USERS_DB_URI: Database URI for user/permission storage.
        OIDC_CLIENT_ID: OAuth client ID.
        OIDC_CLIENT_SECRET: OAuth client secret (sensitive).
        ... and more (see source for full list)
    """

    def __init__(self) -> None:
        """Initialize configuration from the provider chain."""
        # Permission settings
        # Deny by default (issue #293). A resource with no user, group, regex or
        # group-regex grant is not reachable. This shipped as MANAGE, which made a fresh
        # install open by default — every authenticated user could read, edit and delete
        # every experiment and model until grants existed — and silently defeated
        # RESTRICT_RESOURCE_CREATION. Set this to MANAGE explicitly to keep the old
        # behaviour; see "Migrating to deny-by-default" in docs/permissions.md.
        self.DEFAULT_MLFLOW_PERMISSION = config_manager.get("DEFAULT_MLFLOW_PERMISSION", "NO_PERMISSIONS")
        # Opt-in: enforce permission checks on experiment/registered-model creation.
        # When enabled, a user needs EDIT+ (via name regex / group-regex, with a workspace
        # fallback) to create. Off by default, matching upstream MLflow (anyone can create).
        self.RESTRICT_RESOURCE_CREATION = config_manager.get_bool("RESTRICT_RESOURCE_CREATION", default=False)
        self.PERMISSION_SOURCE_ORDER = config_manager.get_list("PERMISSION_SOURCE_ORDER", default=["user", "group", "regex", "group-regex"])

        # Security settings (secrets - may come from Secrets Manager/Key Vault)
        _secret_key = config_manager.get("SECRET_KEY")
        if not _secret_key:
            logger.warning(
                "SECRET_KEY is not configured — using a random key. "
                "Sessions will not survive restarts and will be invalid across replicas. "
                "Set the SECRET_KEY environment variable for production deployments."
            )
            _secret_key = secrets.token_hex(16)
        self.SECRET_KEY = _secret_key
        self.OIDC_CLIENT_SECRET = config_manager.get("OIDC_CLIENT_SECRET")

        # Session cookie settings
        self.SESSION_COOKIE_NAME = config_manager.get("SESSION_COOKIE_NAME", "session")
        self.SESSION_COOKIE_MAX_AGE_SECONDS = config_manager.get_int("SESSION_COOKIE_MAX_AGE_SECONDS", default=14 * 24 * 60 * 60) or None
        _session_cookie_samesite = config_manager.get("SESSION_COOKIE_SAMESITE", "lax").lower()
        if _session_cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError(f"Invalid SESSION_COOKIE_SAMESITE value: '{_session_cookie_samesite}'")
        self.SESSION_COOKIE_SAMESITE = _session_cookie_samesite
        self.SESSION_COOKIE_SECURE = config_manager.get_bool("SESSION_COOKIE_SECURE", default=False)

        # Database settings (sensitive)
        self.OIDC_USERS_DB_URI = config_manager.get("OIDC_USERS_DB_URI", "sqlite:///auth.db")

        # OIDC provider settings
        self.OIDC_DISCOVERY_URL = config_manager.get("OIDC_DISCOVERY_URL")
        self.OIDC_CLIENT_ID = config_manager.get("OIDC_CLIENT_ID")
        # OIDC_REDIRECT_URI: If not set, will be calculated dynamically based on request headers
        # This enables automatic proxy path detection for OIDC callbacks
        self.OIDC_REDIRECT_URI = config_manager.get("OIDC_REDIRECT_URI")
        # Space-delimited per OAuth 2.0 (RFC 6749 §3.3). Comma-separated values are also
        # accepted for backward compatibility and normalized in oauth._build_scope (#238).
        self.OIDC_SCOPE = config_manager.get("OIDC_SCOPE", "openid email profile")
        self.OIDC_PROVIDER_DISPLAY_NAME = config_manager.get("OIDC_PROVIDER_DISPLAY_NAME", "Login with OIDC")
        self.OIDC_GROUPS_ATTRIBUTE = config_manager.get("OIDC_GROUPS_ATTRIBUTE", "groups")
        self.OIDC_AUDIENCE = config_manager.get("OIDC_AUDIENCE")

        # Session re-authentication settings
        # When True, the session is rejected once the IdP-issued access/ID token expires.
        # Leeway compensates for clock skew between this server and the IdP.
        self.OIDC_SESSION_EXPIRY_LEEWAY_SECONDS = config_manager.get_int("OIDC_SESSION_EXPIRY_LEEWAY_SECONDS", default=30)
        # When True, request `offline_access` and persist the refresh token so the
        # session can be silently refreshed against the IdP on expiry. Many enterprises
        # require additional approval for offline_access, so this is opt-in.
        self.OIDC_USE_REFRESH_TOKEN = config_manager.get_bool("OIDC_USE_REFRESH_TOKEN", default=False)

        # JWKS caching settings
        self.OIDC_JWKS_CACHE_TTL_SECONDS = config_manager.get_int("OIDC_JWKS_CACHE_TTL_SECONDS", default=300)

        # HTTP timeout for OIDC discovery and JWKS fetches (seconds). Without
        # this, a hung IdP can block request threads until the OS-level TCP
        # timeout (~2 minutes), causing cascading auth failures.
        self.OIDC_HTTP_TIMEOUT_SECONDS = config_manager.get_int("OIDC_HTTP_TIMEOUT_SECONDS", default=10)
        # TLS verification for OIDC discovery/JWKS and the token endpoint. Default True;
        # only disable for providers with self-signed certs in trusted networks.
        self.OIDC_VERIFY_SSL = config_manager.get_bool("OIDC_VERIFY_SSL", default=True)
        # PKCE code challenge method (e.g. "S256"). None disables PKCE.
        self.OIDC_CODE_CHALLENGE = config_manager.get("OIDC_CODE_CHALLENGE", None)

        # Permission cache settings
        self.PERMISSION_CACHE_TTL_SECONDS = config_manager.get_int("PERMISSION_CACHE_TTL_SECONDS", default=30)

        # username source
        self.OIDC_USERNAME_FIELD = config_manager.get_list("OIDC_USERNAME_FIELD", default=["email", "preferred_username"])
        self.OIDC_DISPLAY_NAME_FIELD = config_manager.get_list("OIDC_DISPLAY_NAME_FIELD", default=["name"])

        # Group settings. OIDC_GROUP_NAME accepts exact names or shell-style patterns.
        self.OIDC_GROUP_NAME = config_manager.get_list("OIDC_GROUP_NAME", default=["mlflow"])
        self.OIDC_ADMIN_GROUP_NAME = config_manager.get_list("OIDC_ADMIN_GROUP_NAME", default=["mlflow-admin"])
        self.OIDC_GROUP_DETECTION_PLUGIN = config_manager.get("OIDC_GROUP_DETECTION_PLUGIN")
        # Optional issuer (iss) validation for JWTs. When set, tokens must carry a matching
        # iss claim. Also a required precondition for bearer auto-provisioning below.
        self.OIDC_ISSUER = config_manager.get("OIDC_ISSUER")
        # Issue #262: auto-provision a permission-DB record on first bearer authentication
        # for API-first users who never logged in via the browser. Opt-in and hardened:
        # requires OIDC_AUDIENCE and OIDC_ISSUER to be set so only aud/iss-scoped tokens
        # can provision. Provisioned users are non-admin and must pass the same group
        # authorization gate as interactive login.
        self.OIDC_PROVISION_ON_BEARER_AUTH = config_manager.get_bool("OIDC_PROVISION_ON_BEARER_AUTH", default=False)
        # Whether a bearer token may confer admin (via OIDC_ADMIN_GROUP_NAME membership in
        # its group claim). Default False: admin is never granted from a token. Only enable
        # if the IdP, not the subject, controls the groups claim on aud-restricted tokens.
        self.OIDC_TRUST_BEARER_GROUP_CLAIMS = config_manager.get_bool("OIDC_TRUST_BEARER_GROUP_CLAIMS", default=False)

        # Database migration settings
        self.OIDC_ALEMBIC_VERSION_TABLE = config_manager.get("OIDC_ALEMBIC_VERSION_TABLE", "alembic_version")

        # UI settings
        self.EXTEND_MLFLOW_MENU = config_manager.get_bool("EXTEND_MLFLOW_MENU", default=True)
        # Inject a small script into MLflow's index.html that forces a full reload on
        # any 401 response, so expired sessions trigger the IdP redirect flow instead
        # of leaving the user staring at empty SPA pages.
        self.EXTEND_MLFLOW_REAUTH = config_manager.get_bool("EXTEND_MLFLOW_REAUTH", default=True)
        self.DEFAULT_LANDING_PAGE_IS_PERMISSIONS = config_manager.get_bool("DEFAULT_LANDING_PAGE_IS_PERMISSIONS", default=True)
        self.AUTOMATIC_LOGIN_REDIRECT = config_manager.get_bool("AUTOMATIC_LOGIN_REDIRECT", default=False)

        # Feature flags
        self.OIDC_GEN_AI_GATEWAY_ENABLED = config_manager.get_bool("OIDC_GEN_AI_GATEWAY_ENABLED", default=True)

        # Workspace feature flags
        self.MLFLOW_ENABLE_WORKSPACES = config_manager.get_bool("MLFLOW_ENABLE_WORKSPACES", default=False)

        # Workspace cache settings
        self.WORKSPACE_CACHE_MAX_SIZE = config_manager.get_int("WORKSPACE_CACHE_MAX_SIZE", default=1024)
        self.WORKSPACE_CACHE_TTL_SECONDS = config_manager.get_int("WORKSPACE_CACHE_TTL_SECONDS", default=300)

        # Proxy trust settings
        self.TRUSTED_PROXIES = config_manager.get_list("TRUSTED_PROXIES", default=[])

        # Cache backend settings
        # "local" (default, in-process TTLCache) or "redis" (shared across replicas)
        self.CACHE_BACKEND = config_manager.get("CACHE_BACKEND", "local")
        self.CACHE_REDIS_URL = config_manager.get("CACHE_REDIS_URL")
        self.CACHE_KEY_PREFIX = config_manager.get("CACHE_KEY_PREFIX", "mlflow_oidc_auth:")

        # Database connection pool settings (auth DB only — separate from MLflow tracking store)
        # These are passed to SQLAlchemy's create_engine().  A value of 0 / None
        # means "use SQLAlchemy defaults".  SQLite ignores pool_size/max_overflow.
        self.DB_POOL_SIZE = config_manager.get_int("OIDC_DB_POOL_SIZE", default=0)
        self.DB_POOL_MAX_OVERFLOW = config_manager.get_int("OIDC_DB_POOL_MAX_OVERFLOW", default=0)
        self.DB_POOL_RECYCLE_SECONDS = config_manager.get_int("OIDC_DB_POOL_RECYCLE_SECONDS", default=0)

        # OIDC workspace detection settings
        self.OIDC_WORKSPACE_CLAIM_NAME = config_manager.get("OIDC_WORKSPACE_CLAIM_NAME", "workspace")
        self.OIDC_WORKSPACE_DETECTION_PLUGIN = config_manager.get("OIDC_WORKSPACE_DETECTION_PLUGIN")
        self.OIDC_WORKSPACE_DEFAULT_PERMISSION = config_manager.get("OIDC_WORKSPACE_DEFAULT_PERMISSION", "NO_PERMISSIONS")
        self.OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT = config_manager.get_bool("OIDC_WORKSPACE_REQUIRE_CREATION_CONTEXT", default=False)
        self.OIDC_WORKSPACE_DENY_DEFAULT_CREATION = config_manager.get_bool("OIDC_WORKSPACE_DENY_DEFAULT_CREATION", default=False)

        # Audit logging settings
        self.AUDIT_LOG_ENABLED = config_manager.get_bool("AUDIT_LOG_ENABLED", default=True)
        self.AUDIT_LOG_LEVEL = config_manager.get("AUDIT_LOG_LEVEL", "INFO")

        # API documentation settings
        self.ENABLE_API_DOCS = config_manager.get_bool("ENABLE_API_DOCS", default=False)

        # Run last: these read settings loaded above.
        self._warn_if_resource_creation_restriction_is_inert()
        self._warn_if_default_permission_is_permissive()
        self._warn_if_username_field_unusable()
        self._warn_if_group_name_unusable()

    @staticmethod
    def _has_usable_entry(field_list) -> bool:
        """Return True if field_list contains at least one non-blank string.

        Shared by every "is this list-of-names config usable" startup check below.
        Defends against two footguns of the underlying config_manager.get_list():
        a comma-split value of "" resolves to [""] rather than [], and a
        provider-supplied list (e.g. from JSON in a secret) may contain non-string
        or None entries. Never raises — every input, including a non-iterable
        value from a misbehaving config provider, is simply "not usable".
        """
        try:
            return any(isinstance(field, str) and field.strip() for field in field_list)
        except TypeError:
            return False

    def _warn_if_username_field_unusable(self) -> None:
        """Warn at startup when OIDC_USERNAME_FIELD or OIDC_DISPLAY_NAME_FIELD is unusable.

        Both are lists of claim names tried in order against the OIDC userinfo/token
        payload; a list with no usable entry means no field can ever be found, so every
        OIDC login (and, for OIDC_USERNAME_FIELD, every bearer-token authentication too)
        fails for every user. That failure only surfaces on the first real login attempt
        in production — warn here instead so a typo'd or emptied config value (e.g. from
        a misconfigured secret provider) is caught before anyone tries to sign in.

        This deliberately warns rather than raises, unlike SESSION_COOKIE_SAMESITE above.
        AppConfig() is a module-level singleton imported by tooling that has nothing to
        do with OIDC login (e.g. the Alembic migration environment in
        db/migrations/env.py), so raising here would take that unrelated tooling down
        too. It matches the existing precedent for "OIDC is completely unusable" failures
        elsewhere in this plugin: OIDC_DISCOVERY_URL is validated lazily on first JWKS
        fetch (auth.py), and a failed OIDC client registration at ASGI lifespan startup
        (app.py's `lifespan`) only logs a warning and lets the app come up — OIDC-specific
        breakage is surfaced without ever taking down the whole process.
        """
        if not self._has_usable_entry(self.OIDC_USERNAME_FIELD):
            logger.warning("OIDC_USERNAME_FIELD is empty; no OIDC login or bearer-token authentication will be able to resolve a username.")
        if not self._has_usable_entry(self.OIDC_DISPLAY_NAME_FIELD):
            logger.warning("OIDC_DISPLAY_NAME_FIELD is empty; no OIDC login will be able to resolve a display name.")

    def _warn_if_group_name_unusable(self) -> None:
        """Warn at startup when OIDC_GROUP_NAME or OIDC_ADMIN_GROUP_NAME is unusable.

        Both are lists of group names matched against the groups claim to decide
        whether a user may log in (OIDC_GROUP_NAME) or is an admin (OIDC_ADMIN_GROUP_NAME).
        Like OIDC_USERNAME_FIELD/OIDC_DISPLAY_NAME_FIELD above, `OIDC_GROUP_NAME=""`
        resolves to [""] via get_list rather than [] and would otherwise silently
        deny every non-admin user with no signal at startup — a login-time symptom
        (every user rejected as "not in an allowed group") with no config-time warning
        to point an operator at the cause. Warns rather than raises for the same
        reason as _warn_if_username_field_unusable: this is a module-level singleton
        imported by tooling that has nothing to do with OIDC login.
        """
        if not self._has_usable_entry(self.OIDC_GROUP_NAME):
            logger.warning("OIDC_GROUP_NAME is empty; no user will ever be recognized as a member of an allowed group and be able to log in.")
        if not self._has_usable_entry(self.OIDC_ADMIN_GROUP_NAME):
            logger.warning("OIDC_ADMIN_GROUP_NAME is empty; no user will ever be granted admin access via group membership.")

    def _warn_if_default_permission_is_permissive(self) -> None:
        """Announce that an open-by-default deployment will change on the next major.

        DEFAULT_MLFLOW_PERMISSION decides access when a resource has no user, group, regex
        or group-regex grant. Shipping MANAGE means a fresh install is open by default:
        every authenticated user can read, edit and delete every experiment and model
        until grants exist. That default is changing to NO_PERMISSIONS (issue #293), which
        is a breaking change for anyone relying on it.

        Warned at startup so the change is not a surprise on upgrade, and so operators can
        act on it while the current release still behaves permissively. The counters added
        alongside this (get_permission_fallback_counts) show how much access is actually
        coming from the fallback in a running deployment.

        Silent when the deployment is unaffected: a default that grants nothing, or
        workspaces enabled — with workspaces, workspace permissions take the fallback role
        and the global default is not consulted as a resource fallback at all.
        """
        if self.MLFLOW_ENABLE_WORKSPACES:
            return

        from mlflow_oidc_auth.permissions import get_permission

        try:
            default_permission = get_permission(self.DEFAULT_MLFLOW_PERMISSION)
        except Exception:
            return

        if not default_permission.can_read:
            return

        logger.warning(
            f"DEFAULT_MLFLOW_PERMISSION={self.DEFAULT_MLFLOW_PERMISSION} grants access to every resource that has no "
            "explicit permission, so any authenticated user can reach resources nobody granted them. "
            "This default becomes NO_PERMISSIONS in the next major version (issue #293). "
            "See docs/permissions.md 'Migrating to deny-by-default' — set the value explicitly now to pin "
            "current behaviour, or create the grants your users rely on before upgrading."
        )

    def _warn_if_resource_creation_restriction_is_inert(self) -> None:
        """Warn when RESTRICT_RESOURCE_CREATION is enabled but cannot deny anything.

        The creation validators require EDIT+ on the resource NAME, resolved from name
        regex and group-regex rules with a workspace fallback. When workspaces are off and
        no regex matches, that resolution lands on DEFAULT_MLFLOW_PERMISSION — which ships
        as MANAGE, and MANAGE grants can_update. So enabling the flag on a default install
        denies nothing at all: every user can still create every experiment and registered
        model, exactly as before.

        A flag that silently does nothing is worse than no flag, because operators
        reasonably read "RESTRICT_RESOURCE_CREATION=true" as "creation is restricted" and
        stop looking. This is documented in docs/permissions.md, and the documentation
        evidently was not enough — hence a startup warning (issue #293).

        Warn rather than refuse to start: this combination is not dangerous in itself, and
        refusing would take down running deployments on upgrade over a configuration that
        was already ineffective.
        """
        if not self.RESTRICT_RESOURCE_CREATION or self.MLFLOW_ENABLE_WORKSPACES:
            return

        # Imported here: mlflow_oidc_auth.permissions imports this module, so a top-level
        # import would be circular.
        from mlflow_oidc_auth.permissions import get_permission

        try:
            default_permission = get_permission(self.DEFAULT_MLFLOW_PERMISSION)
        except Exception:
            # An invalid value is reported elsewhere; nothing useful to say here.
            return

        if default_permission.can_update:
            logger.warning(
                f"RESTRICT_RESOURCE_CREATION is enabled but has no effect: workspaces are disabled and "
                f"DEFAULT_MLFLOW_PERMISSION={self.DEFAULT_MLFLOW_PERMISSION} already grants create rights, "
                "so a name matching no regex rule can still be created by anyone. "
                "Set DEFAULT_MLFLOW_PERMISSION below EDIT (e.g. NO_PERMISSIONS) so only regex or "
                "group-regex matches may create, or enable workspaces and use the workspace creation gate."
            )

    def refresh(self) -> None:
        """Reload configuration from all providers.

        Call this method to reload configuration after secret rotation
        or configuration changes.
        """
        config_manager.refresh()
        self.__init__()


config = AppConfig()
