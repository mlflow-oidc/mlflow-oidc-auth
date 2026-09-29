#!/usr/bin/env python
"""Compare proxied artifact downloads with and without the plugin (issue #152).

Starts two ``mlflow server`` processes against the same S3 endpoint — plain MLflow and MLflow
with ``--app-name oidc-auth`` — both with ``--serve-artifacts``, so every byte goes through the
server. Logs one large artifact and a directory of small ones to each, then times:

``curl``
    Raw HTTP GET of the large artifact. The server's own cost, without client overhead.
``large``
    ``mlflow.artifacts.download_artifacts`` of the large artifact, as a user would.
``small``
    The same for the directory of small files: one request per file, so per-request
    authentication and authorization cost shows up here.
``concurrent``
    ``--concurrency`` parallel raw GETs of the large artifact. Catches a bridge that
    serializes requests.

The plugin side runs as a non-admin user holding ``READ`` on the experiment, so every request
takes the full permission check. The two columns should be close; issue #152 was a 10x gap
(MLflow < 3.8 streamed binary files line by line — see
``mlflow_oidc_auth/tests/perf/test_artifact_streaming.py``).

Any S3-compatible endpoint works. RustFS is the quickest to run locally::

    docker run -d --name rustfs -p 9000:9000 -e RUSTFS_ACCESS_KEY=rustfsadmin \\
        -e RUSTFS_SECRET_KEY=rustfsadmin rustfs/rustfs:latest

    python scripts/bench_artifact_download.py --s3-endpoint http://127.0.0.1:9000 \\
        --access-key rustfsadmin --secret-key rustfsadmin

Everything the script creates (databases, payloads, server logs) lives in one temporary
directory that is removed on exit; the bucket keeps the uploaded objects under a unique prefix.
Note the large artifact is written three times: the payload, the server's upload spool and the
server's download temp file — keep ``--size-mb`` well below the free disk.
"""

import argparse
import contextlib
import json
import os
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BUCKET_DEFAULT = "mlflow-bench"
USER = "bench-user"
ADMIN = "bench-admin"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _s3_env(args) -> Dict[str, str]:
    return {
        "AWS_ACCESS_KEY_ID": args.access_key,
        "AWS_SECRET_ACCESS_KEY": args.secret_key,
        "AWS_DEFAULT_REGION": args.region,
        "MLFLOW_S3_ENDPOINT_URL": args.s3_endpoint,
        "MLFLOW_DISABLE_AGENT_HINT": "1",
    }


def _plugin_env(workdir: Path, port: int) -> Dict[str, str]:
    """The plugin's settings. OIDC is configured only far enough to start; login is never used."""
    return {
        "OIDC_USERS_DB_URI": f"sqlite:///{workdir / 'auth.db'}",
        "SECRET_KEY": uuid.uuid4().hex + uuid.uuid4().hex,
        "OIDC_DISCOVERY_URL": "https://bench.invalid/.well-known/openid-configuration",
        "OIDC_CLIENT_ID": "bench",
        "OIDC_CLIENT_SECRET": "bench-not-a-credential",
        "OIDC_REDIRECT_URI": f"http://127.0.0.1:{port}/callback",
        "LOG_LEVEL": "ERROR",
    }


def _ensure_bucket(args) -> None:
    import boto3

    s3 = boto3.client("s3", endpoint_url=args.s3_endpoint, aws_access_key_id=args.access_key, aws_secret_access_key=args.secret_key, region_name=args.region)
    if args.bucket not in {b["Name"] for b in s3.list_buckets().get("Buckets", [])}:
        s3.create_bucket(Bucket=args.bucket)


def _start_server(name: str, port: int, workdir: Path, env: Dict[str, str], destination: str, plugin: bool) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-m",
        "mlflow",
        "server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--backend-store-uri",
        f"sqlite:///{workdir / f'{name}.db'}",
        "--artifacts-destination",
        destination,
        "--workers",
        "1",
    ]
    if plugin:
        cmd[4:4] = ["--app-name", "oidc-auth"]
    # The child gets its own copy of the descriptor, so the parent's can close once it has started.
    with open(workdir / f"{name}.log", "wb") as log:
        return subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def _wait_healthy(port: int, proc: subprocess.Popen, log: Path, timeout: float = 120) -> None:
    import requests

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server on :{port} exited; see {log}:\n{log.read_text()[-2000:]}")
        # Refused connections are expected until the server binds its port.
        with contextlib.suppress(requests.RequestException):
            if requests.get(f"http://127.0.0.1:{port}/health", timeout=2).status_code == 200:
                return
        time.sleep(1)
    raise RuntimeError(f"server on :{port} did not become healthy in {timeout}s; see {log}")


def _seed_users(env: Dict[str, str]) -> Dict[str, str]:
    """Create an admin and a user with access tokens, in a child process that reads the plugin env."""
    code = f"""
import json
from datetime import datetime, timedelta, timezone
from mlflow_oidc_auth.store import store
expires = datetime.now(timezone.utc) + timedelta(hours=4)
out = {{}}
for username, admin in (({ADMIN!r}, True), ({USER!r}, False)):
    store.create_user(username, username, is_admin=admin)
    out[username] = store.create_user_token(username, "bench", expires, None)[1]
print(json.dumps(out))
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def _grant_read(env: Dict[str, str], experiment_id: str) -> None:
    code = f"from mlflow_oidc_auth.store import store; store.create_experiment_permission({experiment_id!r}, {USER!r}, 'READ')"
    subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)


def _log_artifacts(port: int, auth: Optional[Tuple[str, str]], payload: Path, small_dir: Path) -> Tuple[str, str]:
    """Log the large payload and the small files in one run. Returns (experiment_id, run_id)."""
    code = f"""
import mlflow
mlflow.set_tracking_uri("http://127.0.0.1:{port}")
mlflow.set_experiment("bench-artifact-download")
with mlflow.start_run() as run:
    mlflow.log_artifact({str(payload)!r}, "model")
    mlflow.log_artifacts({str(small_dir)!r}, "small")
print(run.info.experiment_id, run.info.run_id)
"""
    env = dict(os.environ)
    if auth:
        env.update(MLFLOW_TRACKING_USERNAME=auth[0], MLFLOW_TRACKING_PASSWORD=auth[1])
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    experiment_id, run_id = result.stdout.strip().splitlines()[-1].split()
    return experiment_id, run_id


def _raw_get(url: str, auth: Optional[Tuple[str, str]]) -> Tuple[float, int]:
    import requests

    start = time.perf_counter()
    size = 0
    with requests.get(url, auth=auth, stream=True, timeout=600) as response:
        response.raise_for_status()
        for chunk in response.iter_content(1 << 20):
            size += len(chunk)
    return time.perf_counter() - start, size


def _client_download(port: int, auth: Optional[Tuple[str, str]], run_id: str, artifact_path: str, workdir: Path) -> float:
    dst = tempfile.mkdtemp(dir=workdir)
    code = f"""
import time, mlflow
mlflow.set_tracking_uri("http://127.0.0.1:{port}")
start = time.perf_counter()
mlflow.artifacts.download_artifacts(run_id={run_id!r}, artifact_path={artifact_path!r}, dst_path={dst!r})
print(time.perf_counter() - start)
"""
    env = dict(os.environ)
    if auth:
        env.update(MLFLOW_TRACKING_USERNAME=auth[0], MLFLOW_TRACKING_PASSWORD=auth[1])
    try:
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
        return float(result.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(dst, ignore_errors=True)


def _measure(label: str, port: int, auth, experiment_id: str, run_id: str, args, workdir: Path) -> Dict[str, List[float]]:
    url = f"http://127.0.0.1:{port}/api/2.0/mlflow-artifacts/artifacts/{experiment_id}/{run_id}/artifacts/model/payload.bin"
    out: Dict[str, List[float]] = {"curl": [], "large": [], "small": [], "concurrent": []}
    for _ in range(args.iterations):
        seconds, size = _raw_get(url, auth)
        if size != args.size_mb << 20:
            raise RuntimeError(f"{label}: downloaded {size} bytes, expected {args.size_mb << 20}")
        out["curl"].append(seconds)
        out["large"].append(_client_download(port, auth, run_id, "model/payload.bin", workdir))
        out["small"].append(_client_download(port, auth, run_id, "small", workdir))
        start = time.perf_counter()
        with ThreadPoolExecutor(args.concurrency) as pool:
            list(pool.map(lambda _: _raw_get(url, auth), range(args.concurrency)))
        out["concurrent"].append(time.perf_counter() - start)
        print(f"  {label}: iteration done", file=sys.stderr, flush=True)
    return out


def _report(results: Dict[str, Dict[str, List[float]]], args) -> str:
    rows = [
        ("curl", f"GET {args.size_mb} MiB"),
        ("large", f"client, {args.size_mb} MiB"),
        ("small", f"client, {args.small_files} x {args.small_kb} KiB"),
        ("concurrent", f"{args.concurrency} parallel GETs"),
    ]
    lines = [
        "| scenario | plain MLflow | with plugin | ratio |",
        "|---|---|---|---|",
    ]
    for key, title in rows:
        plain = statistics.median(results["plain"][key])
        plugin = statistics.median(results["plugin"][key])
        if key in ("curl", "large"):
            cell = lambda s: f"{s:.2f} s ({args.size_mb / s:.0f} MiB/s)"  # noqa: E731
        elif key == "concurrent":
            cell = lambda s: f"{s:.2f} s ({args.size_mb * args.concurrency / s:.0f} MiB/s)"  # noqa: E731
        else:
            cell = lambda s: f"{s:.2f} s"  # noqa: E731
        lines.append(f"| {title} | {cell(plain)} | {cell(plugin)} | {plugin / plain:.2f}x |")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--s3-endpoint", default=os.environ.get("MLFLOW_S3_ENDPOINT_URL", "http://127.0.0.1:9000"))
    parser.add_argument("--access-key", default=os.environ.get("AWS_ACCESS_KEY_ID", "rustfsadmin"))
    parser.add_argument("--secret-key", default=os.environ.get("AWS_SECRET_ACCESS_KEY", "rustfsadmin"))
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    parser.add_argument("--bucket", default=BUCKET_DEFAULT)
    parser.add_argument("--size-mb", type=int, default=100, help="size of the large artifact in MiB (default: 100)")
    parser.add_argument("--small-files", type=int, default=100, help="number of small artifacts (default: 100)")
    parser.add_argument("--small-kb", type=int, default=64, help="size of each small artifact (default: 64)")
    parser.add_argument("--iterations", type=int, default=3, help="repetitions; the median is reported (default: 3)")
    parser.add_argument("--concurrency", type=int, default=4, help="parallel GETs in the concurrent scenario (default: 4)")
    parser.add_argument("--json", type=Path, help="also write the raw timings here")
    parser.add_argument("--keep", action="store_true", help="keep the working directory (databases, server logs)")
    args = parser.parse_args(argv)

    workdir = Path(tempfile.mkdtemp(prefix="bench-artifacts-"))
    prefix = f"s3://{args.bucket}/bench-{uuid.uuid4().hex[:8]}"
    procs: List[subprocess.Popen] = []
    base_env = {**os.environ, **_s3_env(args)}
    os.environ.update(_s3_env(args))
    try:
        _ensure_bucket(args)
        payload = workdir / "payload.bin"
        with open(payload, "wb") as f:
            for _ in range(args.size_mb):
                f.write(os.urandom(1 << 20))
        small_dir = workdir / "small"
        small_dir.mkdir()
        for i in range(args.small_files):
            (small_dir / f"f{i:04d}.bin").write_bytes(os.urandom(args.small_kb << 10))

        plain_port, plugin_port = _free_port(), _free_port()
        plugin_env = {**base_env, **_plugin_env(workdir, plugin_port)}
        tokens = _seed_users(plugin_env)
        procs.append(_start_server("plain", plain_port, workdir, base_env, f"{prefix}/plain", plugin=False))
        procs.append(_start_server("plugin", plugin_port, workdir, plugin_env, f"{prefix}/plugin", plugin=True))
        _wait_healthy(plain_port, procs[0], workdir / "plain.log")
        _wait_healthy(plugin_port, procs[1], workdir / "plugin.log")

        print("logging artifacts...", file=sys.stderr, flush=True)
        plain_run = _log_artifacts(plain_port, None, payload, small_dir)
        plugin_run = _log_artifacts(plugin_port, (ADMIN, tokens[ADMIN]), payload, small_dir)
        _grant_read(plugin_env, plugin_run[0])
        payload.unlink()  # the servers hold their own copies in S3; free the disk before downloading

        results = {
            "plain": _measure("plain", plain_port, None, *plain_run, args, workdir),
            "plugin": _measure("plugin", plugin_port, (USER, tokens[USER]), *plugin_run, args, workdir),
        }
        print(_report(results, args))
        if args.json:
            args.json.write_text(json.dumps({"args": {k: str(v) for k, v in vars(args).items()}, "results": results}, indent=2))
        return 0
    finally:
        for proc in procs:
            # A server that already exited has no process group left to signal.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)
        for proc in procs:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        if args.keep:
            print(f"working directory kept at {workdir}", file=sys.stderr)
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
