"""Kubernetes service-account tokens as a bearer credential (issue #314).

A pod holds a projected service-account token: an ordinary OIDC-shaped JWT, signed by the
cluster, whose ``sub`` is ``system:serviceaccount:<namespace>:<name>``. Validating one is the
same work as validating any other token — #313 already routes by issuer and enforces the
provider's keys, algorithms, issuer and audience — so what is left is everything *around* that:

**Where the keys come from.** A cluster's JWKS is often not reachable the way a public IdP's is.
``system:service-account-issuer-discovery`` is not bound to ``system:unauthenticated`` on most
clusters, and the API server is frequently unreachable from wherever MLflow runs. Three modes,
because in practice deployments need all three:

* ``discovery`` — the public case, an anonymously readable ``/.well-known/openid-configuration``.
* ``inline`` — the operator pastes the JWKS into configuration. No network at all, which is also
  the only mode that works when the cluster is unreachable from the tracking server.
* ``in_cluster`` — fetch from the API server using the pod's own credentials and CA bundle.

**Who the token says it is.** ``sub`` is parsed rather than used verbatim: a username of
``system:serviceaccount:team-a:trainer`` is unusable in a UI and collides with nothing, so a
template turns it into something an operator can read and grant permissions to.

**Whether it may be provisioned.** A service-account token carries no groups claim, so the group
gate that guards OIDC bearer provisioning cannot apply. A namespace allowlist takes its place —
without one, *every* pod in the cluster that can read a projected token becomes an MLflow user.

The ``TokenReview`` alternative is evaluated in ``docs/kubernetes-auth.md`` and deliberately not
implemented; the short version is that it turns every authenticated request into a synchronous
call to the API server.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()

#: ``sub`` of a projected service-account token.
SERVICE_ACCOUNT_SUBJECT = re.compile(r"^system:serviceaccount:(?P<namespace>[^:]+):(?P<name>[^:]+)$")

#: Kubernetes object names are DNS labels, and namespaces likewise. Anchored and bounded so a
#: crafted ``sub`` cannot smuggle punctuation into a username, a group name or a template.
DNS_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
MAX_LABEL_LENGTH = 63

#: Username shape. Fixed rather than configurable, and separated by ``.`` rather than ``-``.
#:
#: ``-`` is legal *inside* a DNS label, so ``{namespace}-{name}`` is ambiguous: namespace
#: ``prod-etl`` with account ``writer`` and namespace ``prod`` with account ``etl-writer`` both
#: render ``prod-etl-writer``. Anyone who can create a service account in one allowlisted
#: namespace could then collide with an account in another and inherit its permissions. ``.``
#: cannot appear in a label, so the two halves stay distinguishable.
USERNAME_TEMPLATE = "{name}.{namespace}@serviceaccount.cluster.local"

#: Group. Namespace-derived, so permissions can be granted to a whole team's namespace
#: rather than to each service account in it.
GROUP_TEMPLATE = "k8s:{namespace}"

#: Where a pod finds its own credentials and the API server's CA.
IN_CLUSTER_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
IN_CLUSTER_CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


class ServiceAccountError(Exception):
    """A token that is not a usable Kubernetes service-account credential."""


@dataclass(frozen=True)
class ServiceAccount:
    """The identity a projected token asserts.

    Attributes:
        namespace: Kubernetes namespace the service account lives in.
        name: Service account name.
    """

    namespace: str
    name: str

    @property
    def username(self) -> str:
        """The MLflow username for this service account."""
        return USERNAME_TEMPLATE.format(namespace=self.namespace, name=self.name)

    @property
    def group(self) -> str:
        """The group standing for this service account's namespace."""
        return GROUP_TEMPLATE.format(namespace=self.namespace)


def valid_dns_label(value: Any) -> bool:
    """Whether ``value`` is a Kubernetes object name.

    Shared with the registry deliberately: an allowlist entry is compared against a namespace
    that came through :func:`parse_service_account`, so the two must agree on what a namespace
    can look like or an entry silently never matches.
    """
    return isinstance(value, str) and bool(value) and len(value) <= MAX_LABEL_LENGTH and bool(DNS_LABEL.match(value))


def parse_service_account(subject: Any) -> ServiceAccount:
    """Parse ``sub`` into a namespace and a service-account name.

    Both halves are validated as DNS labels rather than accepted as written. The claim is signed,
    so a cluster cannot be tricked into asserting a malformed ``sub`` — but a *compromised or
    hostile* cluster that a deployment has (perhaps unwisely) configured as a provider could,
    and the value goes on to become a username and a group name. Anything outside the character
    set Kubernetes itself allows is refused here rather than rendered into an identifier.

    Parameters:
        subject: The token's ``sub`` claim.

    Returns:
        The parsed :class:`ServiceAccount`.

    Raises:
        ServiceAccountError: If ``sub`` is not a well-formed service-account subject.
    """
    if not isinstance(subject, str):
        raise ServiceAccountError(f"service-account subject must be a string, got {type(subject).__name__}")

    match = SERVICE_ACCOUNT_SUBJECT.match(subject)
    if not match:
        raise ServiceAccountError("token subject is not 'system:serviceaccount:<namespace>:<name>'")

    namespace, name = match.group("namespace"), match.group("name")
    if not valid_dns_label(namespace) or not valid_dns_label(name):
        raise ServiceAccountError("service-account namespace and name must be DNS labels")

    return ServiceAccount(namespace=namespace, name=name)


def namespace_is_allowed(namespace: str, allowlist: Tuple[str, ...]) -> bool:
    """Whether ``namespace`` may be provisioned.

    An empty allowlist means **no**, never "all". A service-account token carries no group claim,
    so nothing else narrows who may become a user: with an empty list treated as permissive,
    every pod in the cluster that can read its own projected token would become an MLflow user
    the moment the provider was configured.
    """
    return namespace in allowlist


def load_inline_jwks(raw: Any) -> Dict[str, Any]:
    """Validate an operator-supplied JWKS, given as a mapping or a JSON string.

    Raises:
        ValueError: If it is not a JWKS-shaped object with a non-empty ``keys`` list.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"inline JWKS is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("keys"), list) or not raw["keys"]:
        raise ValueError("inline JWKS must be an object with a non-empty 'keys' list")

    return raw


def in_cluster_credentials(token_path: str = IN_CLUSTER_TOKEN_PATH, ca_path: str = IN_CLUSTER_CA_PATH) -> Tuple[Optional[str], Optional[str]]:
    """The pod's own service-account token and the API server's CA bundle.

    Returns ``(None, None)`` when they are not present, which is the ordinary case when MLflow
    runs outside the cluster — the caller then reports a configuration problem rather than
    failing with a file-not-found from deep inside an HTTP call.
    """
    try:
        with open(token_path, "r", encoding="utf-8") as handle:
            token = handle.read().strip()
    except OSError:
        return None, None

    ca = ca_path if _readable(ca_path) else None
    return (token or None), ca


def _readable(path: str) -> bool:
    try:
        with open(path, "rb"):
            return True
    except OSError:
        return False
