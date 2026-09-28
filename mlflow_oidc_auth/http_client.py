"""Outbound HTTPS that trusts the operating system's certificate store.

The OIDC client (authlib on ``httpx2``) verifies TLS against the operating system's store via
``truststore``. ``requests`` on its own uses certifi's bundle instead, so without this module the
plugin's own calls (bearer-token discovery and JWKS, SAML metadata, the bundled Entra group
plugin) would trust a different set of CAs than the login flow. An enterprise that intercepts
TLS (DLP/DPI) installs its root CA in the operating system's store; certifi never sees it.

With the default ``verify=True``, ``requests`` still loads its CA bundle into the context (certifi's,
or ``REQUESTS_CA_BUNDLE`` / ``CURL_CA_BUNDLE`` when set), so these calls trust the system store in
addition to that bundle. An explicit ``verify=<path>`` (the Kubernetes provider's cluster CA)
keeps its exact meaning: that bundle only, never the system store.
"""

import ssl
from typing import Any

import requests
import truststore
from requests.adapters import HTTPAdapter


def _system_trust_context() -> ssl.SSLContext:
    """A client context on the operating system's trust store that refuses TLS older than 1.2."""
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


class _SystemTrustAdapter(HTTPAdapter):
    """An adapter whose connection pools verify against the operating system's trust store.

    Each adapter gets its own context: urllib3 loads a ``verify=<path>`` bundle into the context
    it is given, so a shared context would carry one call's extra CA into every other call.
    """

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        kwargs["ssl_context"] = _system_trust_context()
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any):
        proxy_kwargs["ssl_context"] = _system_trust_context()
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def system_trust_session() -> requests.Session:
    """Return a new ``requests.Session`` whose HTTPS verification uses the system trust store.

    Use it as a context manager, and finish reading the response (including a streamed one)
    inside the ``with`` block.

    Returns:
        A session with the system-trust adapter mounted for ``https://``.
    """
    session = requests.Session()
    session.mount("https://", _SystemTrustAdapter())
    return session


def get(url: str, *, verify: Any = True, **kwargs: Any) -> requests.Response:
    """``requests.get`` that verifies TLS against the operating system's trust store.

    Parameters:
        url: The URL to fetch.
        verify: ``True`` (system store, plus certifi or ``REQUESTS_CA_BUNDLE``), a CA bundle path
            (that bundle only, as ``requests`` does, so a pinned CA is never widened to the system
            store), or ``False`` (no verification; only for explicitly configured insecure providers).
        **kwargs: Passed to ``requests.Session.get``.

    Returns:
        The response. Its body has been read unless ``stream=True`` was passed, in which case use
        :func:`system_trust_session` instead so the session outlives the read.
    """
    if verify is False:
        # Only reached when an operator explicitly disables verification for a provider.
        return requests.get(url, verify=False, **kwargs)  # nosec B501
    if verify is not True:
        # A pinned CA bundle (e.g. the cluster CA): trust exactly that, as before.
        return requests.get(url, verify=verify, **kwargs)
    with system_trust_session() as session:
        return session.get(url, verify=verify, **kwargs)
