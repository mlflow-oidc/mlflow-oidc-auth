"""Proxied artifact downloads stream in large chunks through the plugin's WSGI bridge (issue #152).

Issue #152 reported downloads through the plugin at ~2 MB/s against ~20 MB/s without it. The
cause was MLflow < 3.8 serving proxied artifacts with ``yield from file_handle``, which iterates a
binary file LINE BY LINE: ~255-byte chunks for binary data, ~410,000 of them per 100 MB. Each
chunk costs a thread-to-event-loop hop in the ASGI->WSGI bridge (~100 us under uvicorn), so a
100 MB model took 40 s. It was fixed upstream in mlflow/mlflow#19520 (MLflow 3.8.0); this plugin
has required a fixed MLflow since v6.0.0.

These tests drive MLflow's real download handler through ``AuthAwareWSGIMiddleware`` — the
bridge every Flask request crosses — and count the ASGI body messages that come out. The handler
is mounted on its own Flask app: MLflow's global app gains the plugin's authorization hooks as
soon as anything imports ``mlflow_oidc_auth.app``, and those are not what is under test here. Chunk
counts, not timings, so the result is deterministic. They fail if either side regresses:
MLflow going back to tiny chunks, or the bridge re-chunking or buffering the whole body.

The payload has a newline every 256 bytes, the shape that made line iteration pathological.
``scripts/bench_artifact_download.py`` measures the same path end to end against a real S3.
"""

import asyncio
from typing import List, Tuple

import pytest
from flask import Flask
from mlflow.server import ARTIFACTS_DESTINATION_ENV_VAR, SERVE_ARTIFACTS_ENV_VAR
from mlflow.server import handlers as mlflow_handlers

from mlflow_oidc_auth.middleware.auth_aware_wsgi_middleware import AuthAwareWSGIMiddleware

# 4 MiB of 256-byte "lines": line iteration would yield 16,384 chunks.
LINE = b"x" * 255 + b"\n"
PAYLOAD = LINE * (4 * 1024 * 1024 // len(LINE))

# The smallest chunk a sane file response uses is werkzeug's 8 KiB FileWrapper block, so a 4 MiB
# body is at most 512 chunks (plus slack for a short last one). Line iteration is 32x over.
MIN_CHUNK = 8 * 1024
MAX_CHUNKS = len(PAYLOAD) // MIN_CHUNK + 2
# No single message may carry more than MLflow's 1 MiB stream chunk: a bridge that buffered the
# whole artifact before sending would hold every download in server memory.
MAX_MESSAGE = 1024 * 1024

ARTIFACT_PATH = "0/run/artifacts/model/big.bin"
DOWNLOAD_ROUTE = "/api/2.0/mlflow-artifacts/artifacts/<path:artifact_path>"


def _download_app() -> Flask:
    """A Flask app serving only MLflow's proxied-artifact download handler, as MLflow routes it."""
    app = Flask(__name__)
    app.add_url_rule(DOWNLOAD_ROUTE, "download_artifact", mlflow_handlers._download_artifact, methods=["GET"])
    return app


@pytest.fixture
def served_artifact(tmp_path, monkeypatch):
    """An MLflow server state serving proxied artifacts from a local destination holding PAYLOAD."""
    destination = tmp_path / "artifacts"
    target = destination / ARTIFACT_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(PAYLOAD)
    monkeypatch.setenv(SERVE_ARTIFACTS_ENV_VAR, "true")
    monkeypatch.setenv(ARTIFACTS_DESTINATION_ENV_VAR, str(destination))
    # MLflow caches the artifact repository in a module global on first use.
    monkeypatch.setattr(mlflow_handlers, "_artifact_repo", None)
    return destination


def _download_through_bridge() -> Tuple[int, List[bytes]]:
    """GET the artifact through AuthAwareWSGIMiddleware; return the status and each body message."""
    path = f"/api/2.0/mlflow-artifacts/artifacts/{ARTIFACT_PATH}"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    }
    status: List[int] = []
    bodies: List[bytes] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])
        elif message["type"] == "http.response.body" and message.get("body"):
            bodies.append(message["body"])

    asyncio.run(AuthAwareWSGIMiddleware(_download_app())(scope, receive, send))
    return status[0], bodies


class TestProxiedDownloadChunking:
    def test_local_destination_streams_in_file_blocks(self, served_artifact):
        """A local artifact destination is served with ``send_file``."""
        status, bodies = _download_through_bridge()

        assert status == 200
        assert b"".join(bodies) == PAYLOAD
        assert len(bodies) <= MAX_CHUNKS, f"{len(bodies)} body messages for {len(PAYLOAD)} bytes: the download is streaming line by line"
        assert max(map(len, bodies)) <= MAX_MESSAGE

    def test_remote_destination_streams_in_file_blocks(self, served_artifact, monkeypatch):
        """A remote store (S3, GCS, Azure) is downloaded to a temp file and streamed from there.

        This is the path issue #152 hit. Reporting no local path sends the handler down it while
        still reading from the test's directory.
        """
        repo = mlflow_handlers._get_artifact_repo_mlflow_artifacts()
        monkeypatch.setattr(repo, "get_local_path", lambda *_args, **_kwargs: None)

        status, bodies = _download_through_bridge()

        assert status == 200
        assert b"".join(bodies) == PAYLOAD
        assert len(bodies) <= MAX_CHUNKS, f"{len(bodies)} body messages for {len(PAYLOAD)} bytes: the download is streaming line by line"
        assert max(map(len, bodies)) <= MAX_MESSAGE

    def test_the_bridge_forwards_chunks_as_the_app_yields_them(self):
        """The bridge neither splits nor merges what the WSGI app yields.

        Pins the bridge half of the contract without MLflow in the picture: 1 MiB in, 1 MiB out.
        """
        chunk = b"\n" * (1024 * 1024)

        def app(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/octet-stream")])
            return iter([chunk] * 4)

        bodies: List[bytes] = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.body" and message.get("body"):
                bodies.append(message["body"])

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "root_path": "",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
        }
        asyncio.run(AuthAwareWSGIMiddleware(app)(scope, receive, send))

        assert [len(b) for b in bodies] == [len(chunk)] * 4
