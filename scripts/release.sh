#!/usr/bin/env bash
export MLFLOW_OIDC_AUTH_VERSION=${1:-0.0.0.dev0}
pushd web-react &&\
yarn install &&\
yarn release &&\
popd &&\
python -m build
