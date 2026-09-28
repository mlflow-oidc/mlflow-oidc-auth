"""Outbound HTTPS trusts the operating system's store, plus any configured CA bundle."""

import datetime
import http.server
import ssl
import threading
from unittest.mock import patch

import pytest
import requests
import truststore
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from mlflow_oidc_auth import http_client


@pytest.fixture(scope="module")
def private_ca_server(tmp_path_factory):
    """An HTTPS server whose certificate chains to a private CA no trust store knows.

    This stands in for an enterprise TLS-inspection root: trusted only once its CA is supplied.
    """
    directory = tmp_path_factory.mktemp("private-ca")
    now = datetime.datetime.now(datetime.timezone.utc)

    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test private root")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    ca_file = directory / "ca.pem"
    ca_file.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_file = directory / "leaf.pem"
    cert_file.write_bytes(leaf_cert.public_bytes(serialization.Encoding.PEM))
    key_file = directory / "leaf.key"
    key_file.write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("localhost", 0), _Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_file, key_file)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"https://localhost:{server.server_address[1]}/", str(ca_file)
    server.shutdown()


@pytest.fixture(autouse=True)
def _no_ca_bundle_env(monkeypatch):
    for name in ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_sessions_verify_with_the_system_trust_store():
    with http_client.system_trust_session() as session:
        adapter = session.get_adapter("https://idp.example.com/")
        assert isinstance(adapter.poolmanager.connection_pool_kw["ssl_context"], truststore.SSLContext)


def test_sessions_refuse_protocols_older_than_tls_1_2():
    with http_client.system_trust_session() as session:
        context = session.get_adapter("https://idp.example.com/").poolmanager.connection_pool_kw["ssl_context"]
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_every_session_gets_its_own_context():
    """A bundle loaded for one call must not become trusted by another."""
    with http_client.system_trust_session() as first, http_client.system_trust_session() as second:
        first_context = first.get_adapter("https://a/").poolmanager.connection_pool_kw["ssl_context"]
        second_context = second.get_adapter("https://a/").poolmanager.connection_pool_kw["ssl_context"]
    assert first_context is not second_context


def test_an_unknown_ca_is_refused(private_ca_server):
    url, _ = private_ca_server
    with pytest.raises(requests.exceptions.SSLError):
        http_client.get(url, timeout=5)


def test_a_ca_bundle_passed_as_verify_is_trusted(private_ca_server):
    url, ca_file = private_ca_server
    assert http_client.get(url, verify=ca_file, timeout=5).json() == {"ok": True}


def test_requests_ca_bundle_is_still_honoured(private_ca_server, monkeypatch):
    url, ca_file = private_ca_server
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", ca_file)
    assert http_client.get(url, timeout=5).json() == {"ok": True}


def test_a_pinned_bundle_is_not_widened_to_the_system_store():
    """verify=<path> means that bundle only (the Kubernetes provider pins the cluster CA)."""
    with patch.object(http_client.requests, "get") as plain_get, patch.object(http_client, "system_trust_session") as session:
        http_client.get("https://kubernetes.default.svc/openid/v1/jwks", verify="/var/run/ca.crt", timeout=5)
    plain_get.assert_called_once_with("https://kubernetes.default.svc/openid/v1/jwks", verify="/var/run/ca.crt", timeout=5)
    session.assert_not_called()


def test_a_bundle_for_one_call_is_not_trusted_by_the_next(private_ca_server):
    url, ca_file = private_ca_server
    assert http_client.get(url, verify=ca_file, timeout=5).status_code == 200
    with pytest.raises(requests.exceptions.SSLError):
        http_client.get(url, timeout=5)


def test_verification_off_is_passed_through_unchanged():
    with patch.object(http_client.requests, "get") as plain_get:
        http_client.get("https://idp.example.com/", verify=False, timeout=5)
    plain_get.assert_called_once_with("https://idp.example.com/", verify=False, timeout=5)
