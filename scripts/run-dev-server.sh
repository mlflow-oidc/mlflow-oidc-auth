#!/usr/bin/env bash
set -e

mlflow=""

# Stop the tracking server. It runs in its own process group (see below), so the
# signal reaches the uvicorn reloader and its worker too, not just the mlflow CLI.
# SIGTERM first so uvicorn shuts down cleanly; SIGKILL only if it hangs.
cleanup() {
  trap - EXIT INT TERM HUP
  # Nothing in here may abort the stop: after a closed terminal (SIGHUP) every echo
  # fails, and under set -e (or SIGPIPE on a closed pipe) that would exit before the
  # server is signalled.
  set +e
  trap '' PIPE
  if [ -n "$mlflow" ] && kill -0 "$mlflow" 2>/dev/null; then
    echo "Stopping tracking server..."
    kill -TERM -- "-$mlflow" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 -- "-$mlflow" 2>/dev/null || break
      sleep 1
    done
    if kill -0 -- "-$mlflow" 2>/dev/null; then
      echo "Tracking server did not stop in 10s, killing it"
      kill -KILL -- "-$mlflow" 2>/dev/null || true
    fi
    wait "$mlflow" 2>/dev/null || true
  fi
}

python_preconfigure() {
  if [ ! -d venv ]; then
    python3 -m venv venv
    source venv/bin/activate
    python3 -m pip install --upgrade pip
    python3 -m pip install build setuptools
    python3 -m pip install --editable=".[full, caching-redis]"
  fi
}

check_yarn_and_node_version() {
  if ! command -v node &> /dev/null; then
    echo "node is not installed. Please install node to continue."
    exit 1
  fi

  if ! command -v yarn &> /dev/null; then
    echo "yarn is not installed. Please install yarn to continue."
    exit 1
  fi

  node_version=$(node --version)

  major=$(echo $node_version | cut -d. -f1 | tr -d 'v')
  minor=$(echo $node_version | cut -d. -f2)
  patch=$(echo $node_version | cut -d. -f3)

  if ! { [ "$major" -eq 14 ] && [ "$minor" -eq 15 ] && [ "$patch" -eq 0 ]; } && ! { [ "$major" -ge 16 ] && { [ "$minor" -ge 10 ] || [ "$major" -gt 16 ]; }; }; then
    echo "Node version $node_version is not supported. Please install node version ^14.15.0 || >=16.10.0 to continue."
    exit 1
  fi
}

ui_preconfigure() {
  if [ ! -d "web-react/node_modules" ]; then
    pushd web-react
    yarn install
    popd
  fi
}

wait_server_ready() {
  for backoff in 0 1 1 2 3 5 8 13 21; do
    echo "Waiting for tracking server to be ready..."
    sleep $backoff
    if curl --fail --silent --show-error --output /dev/null $1; then
      echo "Server is ready"
      return 0
    fi
  done
  echo -e "\nFailed to launch tracking server"
  return 1
}

# Registered before anything starts: Ctrl-C, a closed terminal, a failed health
# check (set -e) and yarn exiting all end up in cleanup.
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

check_yarn_and_node_version
python_preconfigure
source venv/bin/activate
# Job control on for this one command: the server gets its own process group, whose
# id is its pid, so cleanup can signal the whole tree at once.
set -m
mlflow --env-file .env server --uvicorn-opts "--reload --log-level debug" --app-name oidc-auth --host 0.0.0.0 --port 8080 --backend-store-uri=sqlite:///mlflow.db &
mlflow=$!
set +m
wait_server_ready http://localhost:8080/health
ui_preconfigure
yarn --cwd web-react watch
