#!/usr/bin/env bash
set -e

cleanup() {
    echo "Cleaning up..."
    kill $mlflow $ui 2>/dev/null
    exit
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

check_yarn_and_node_version
python_preconfigure
source venv/bin/activate
mlflow server --uvicorn-opts "--reload --log-level debug" --app-name oidc-auth --host 0.0.0.0 --port 8080 --backend-store-uri=sqlite:///mlflow.db &
mlflow=$!
wait_server_ready localhost:8080/
ui_preconfigure
yarn --cwd web-react watch

trap cleanup SIGINT
