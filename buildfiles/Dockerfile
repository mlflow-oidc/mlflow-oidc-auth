ARG PYTHON_VERSION=3.12-slim
FROM python:${PYTHON_VERSION} AS base

LABEL org.opencontainers.image.authors="Alexander Kharkevich <alex@kharkevich.org>"
LABEL org.opencontainers.image.source="https://github.com/mlflow-oidc/mlflow-tracking-server-docker"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.description="MLFlow tracking server with OpenID Connect authentication"

RUN adduser --disabled-password --gecos '' python
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    zlib1g-dev \
    make \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and Yarn for building the UI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g yarn

RUN pip install --no-cache-dir uv wheel

USER python
WORKDIR /mlflow
# podman can't create directories with the right permissions
RUN chown python:python /mlflow

COPY pyproject.toml uv.lock /mlflow/

# First install all dependencies except mlflow-oidc-auth
RUN uv sync --frozen --no-install-project --no-cache

# Copy the local mlflow-oidc-auth package with security fixes
COPY --chown=python:python mlflow_oidc_auth/ /mlflow/mlflow_oidc_auth/
COPY --chown=python:python mlflow_oidc_auth_pyproject.toml /mlflow/pyproject.toml

# Copy web-ui and build it
USER root
COPY web-ui/ /tmp/web-ui/
RUN cd /tmp/web-ui && \
    yarn install && \
    yarn release && \
    chown -R python:python /tmp/web-ui

# Copy the built UI to the mlflow_oidc_auth package
USER python
RUN cp -r /tmp/web-ui/../mlflow_oidc_auth/ui /mlflow/mlflow_oidc_auth/

# Uninstall the PyPI version and install our local version with fixes
RUN cd /mlflow && \
    uv pip uninstall mlflow-oidc-auth && \
    uv pip install -e .[full,caching-redis,fastapi]

FROM base AS final
USER python
WORKDIR /mlflow
COPY --from=builder --chown=python:python /mlflow /mlflow
ENV PATH=/mlflow/.venv/bin:$PATH
ENV OAUTHLIB_INSECURE_TRANSPORT=1
EXPOSE 5000
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--app-name", "oidc-auth", "--backend-store-uri", "sqlite:///mlflow.db", "--default-artifact-root", "/mlflow/artifacts"]
