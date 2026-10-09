# Build image for Anthropic's OSS Scanner (https://github.com/anthropics/oss-scanner).
#
# The scanner builds this with the repository as the build context, with network access, then
# runs the analysis in the finished image with no network. Everything the tests need is fetched
# here. Python follows tox.ini (py314); Node follows CI (.github/workflows/unit-tests.yml).
#
# Inside the image:
#   /src                         the checkout, installed editable with every optional extra
#   /src/mlflow_oidc_auth/ui     the built admin UI (web-react builds into it)
#   PostgreSQL 18                installed, initialised, stopped; see threat_model.md to start it
FROM node:24-trixie-slim AS node

FROM python:3.14-trixie
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Never read a .env from the checkout or the environment the scanner runs in.
    PYTHON_DOTENV_DISABLED=1

# PostgreSQL 18 (as in CI) comes from the PGDG repository, set up with the key Debian's
# postgresql-common ships; it lets the migration tests run against both backends offline.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential postgresql-common procps \
    && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
    && apt-get install -y --no-install-recommends postgresql-18 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install -g yarn@1.22.22

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Python: the extras tox installs (tox.ini [testenv]) plus redis for the cache backend, and the
# PostgreSQL driver the migration tests use. xmlsec and lxml must both be binary wheels: one built
# from source against Debian's libxml2 next to the other's bundled copy fails at import, so a
# missing wheel fails the build here instead of quietly disabling SAML.
RUN pip install --only-binary xmlsec,lxml -e '.[full,test,cache]' psycopg2-binary

# Frontend: install, then build the admin UI into mlflow_oidc_auth/ui/ as a release does.
RUN cd web-react && yarn install --frozen-lockfile && yarn build && yarn cache clean

# A local PostgreSQL for the migration tests (MLFLOW_OIDC_TEST_POSTGRES_URI). Trust auth on the
# loopback only; there is no secret here.
RUN pg_ctlcluster 18 main start \
    && su postgres -c "psql -c \"CREATE ROLE mlflow_oidc LOGIN SUPERUSER\"" \
    && su postgres -c "createdb -O mlflow_oidc mlflow_oidc_test" \
    && pg_ctlcluster 18 main stop \
    && sed -i -E 's/^(host .*)scram-sha-256$/\1trust/' /etc/postgresql/18/main/pg_hba.conf

# Run the suites once so a broken image is visible in the build log, without failing the build.
# The python suite is what CI runs (tox.ini), minus the Keycloak/browser e2e markers. It runs in a
# throwaway copy so the databases and mlruns/ it writes never land in /src, and hooks/ runs file by
# file because the whole directory in one process can hang (AGENTS.md).
RUN pg_ctlcluster 18 main start \
    && cp -a /src /tmp/testrun && cd /tmp/testrun \
    && export MLFLOW_OIDC_TEST_POSTGRES_URI=postgresql+psycopg2://mlflow_oidc@localhost:5432/mlflow_oidc_test \
    && (timeout -k 30 3600 python -m pytest -q -p no:cacheprovider -m "not integration and not e2e" \
          --ignore=mlflow_oidc_auth/tests/hooks mlflow_oidc_auth/tests \
        || echo "WARNING: python tests reported failures") \
    && for f in mlflow_oidc_auth/tests/hooks/test_*.py; do \
         timeout -k 30 600 python -m pytest -q -p no:cacheprovider "$f" || echo "WARNING: $f reported failures"; \
       done \
    && (cd web-react && timeout -k 30 900 yarn test || echo "WARNING: frontend tests reported failures") \
    && cd / && rm -rf /tmp/testrun \
    && pg_ctlcluster 18 main stop
