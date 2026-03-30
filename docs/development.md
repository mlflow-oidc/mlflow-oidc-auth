# Development

This guide covers setting up a local development environment, running tests, and contributing to mlflow-oidc-auth.

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12 (via `.python-version`) | Backend server, tests |
| Node.js | 24+ | Frontend build and tests |
| Yarn | Latest | Frontend package manager |
| Git | Latest | Version control |

The project uses Python 3.12 for development and CI. The minimum supported Python version for end users is 3.10.

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/mlflow-oidc/mlflow-oidc-auth
cd mlflow-oidc-auth
```

### Quick Start (Dev Server Script)

The fastest way to start a local development environment:

```bash
./scripts/run-dev-server.sh
```

This script:
1. Creates a Python virtual environment in `venv/` (if not present)
2. Installs the package in editable mode with all extras
3. Starts the MLflow server with the OIDC auth plugin on `localhost:8080`
4. Waits for the server to be ready
5. Installs frontend dependencies via Yarn (if not present)
6. Starts the Vite watcher for frontend hot-reload

> **Note:** You need a `.env` file with valid OIDC configuration before starting. See [Configuration](configuration.md) for required variables.

### Manual Setup

If you prefer to set up each component individually:

#### Backend

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in editable mode with dev and test dependencies
pip install --upgrade pip
pip install -e ".[dev,test]"

# Create a .env file with your OIDC provider settings
# (see Configuration docs for all variables)

# Start the server with hot-reload
mlflow --env-file .env server \
  --uvicorn-opts "--reload --log-level debug" \
  --app-name oidc-auth \
  --host 0.0.0.0 \
  --port 8080 \
  --backend-store-uri sqlite:///mlflow.db
```

#### Frontend

```bash
# Install dependencies
cd web-react
yarn install

# Development mode (watches for changes, rebuilds into mlflow_oidc_auth/ui/)
yarn watch

# Or start the Vite dev server with HMR (serves on a separate port)
yarn dev
```

The frontend builds into `mlflow_oidc_auth/ui/`, which is served by the FastAPI backend at `/oidc/ui/`.

## Project Structure

```
mlflow-oidc-auth/
├── mlflow_oidc_auth/           # Python package (backend)
│   ├── app.py                  # FastAPI app factory (create_app)
│   ├── auth.py                 # JWT validation, OIDC token handling
│   ├── bridge/                 # FastAPI↔Flask auth context bridge
│   ├── cli.py                  # mlflow-oidc-server CLI command
│   ├── config.py               # AppConfig singleton
│   ├── config_providers/       # Pluggable config sources (AWS, Azure, Vault, K8s)
│   ├── db/                     # Database models and Alembic migrations
│   │   ├── models/             # SQLAlchemy ORM models (SqlUser, SqlGroup, etc.)
│   │   └── migrations/         # Alembic migration scripts
│   ├── dependencies.py         # FastAPI dependency injection
│   ├── entities/               # Domain entity classes (plain Python)
│   ├── exceptions.py           # Exception handlers
│   ├── graphql/                # GraphQL authorization middleware
│   ├── hack.py                 # MLflow UI HTML injection (nav links)
│   ├── hooks/                  # Flask before_request/after_request hooks
│   ├── middleware/             # ASGI middleware (auth, proxy, workspace, WSGI bridge)
│   ├── models/                 # Pydantic request/response models
│   ├── oauth.py                # OIDC/OAuth2 client setup (authlib)
│   ├── permissions.py          # Permission levels (READ, USE, EDIT, MANAGE)
│   ├── plugins/                # Workspace detection plugins
│   ├── repository/             # SQLAlchemy repository classes (CRUD)
│   ├── responses/              # Flask response helpers (legacy)
│   ├── routers/                # FastAPI route handlers (19 routers)
│   ├── sqlalchemy_store.py     # Data access facade (delegates to repositories)
│   ├── store.py                # Store singleton
│   ├── tests/                  # Backend test suite
│   ├── ui/                     # Built frontend assets (generated, not in git)
│   ├── utils/                  # Utility functions
│   └── validators/             # Permission validation logic
├── web-react/                  # Frontend (React + TypeScript)
│   ├── src/
│   │   ├── app.tsx             # Root component, route definitions
│   │   ├── main.tsx            # Entry point
│   │   ├── core/               # Shared hooks, services, context
│   │   ├── features/           # Feature-based modules (experiments, models, etc.)
│   │   ├── shared/             # Shared UI components
│   │   └── tests/              # Test setup
│   ├── package.json
│   ├── vite.config.ts          # Vite build config (outputs to ../mlflow_oidc_auth/ui)
│   ├── tsconfig.json
│   └── eslint.config.js
├── scripts/                    # Development and release scripts
│   ├── run-dev-server.sh       # Local dev environment script
│   ├── release.sh              # Semantic release version bumping
│   ├── docker-compose.yaml     # Redis for cache integration testing
│   ├── postgresql/             # PostgreSQL helper scripts
│   └── mysql/                  # MySQL helper scripts
├── docs/                       # Documentation (Docsify site)
├── pyproject.toml              # Python package metadata, build config
├── tox.ini                     # Test environment configuration
├── .pre-commit-config.yaml     # Pre-commit hook configuration
└── .releaserc                  # Semantic release configuration
```

## Running Tests

### Backend Tests (pytest)

```bash
# Run all unit tests
pytest mlflow_oidc_auth/tests

# Run with coverage
coverage run -m pytest -s -m "not integration" mlflow_oidc_auth/tests
coverage xml

# Run a specific test file
pytest mlflow_oidc_auth/tests/routers/test_auth.py

# Run a specific test class or method
pytest mlflow_oidc_auth/tests/test_sqlalchemy_store.py::TestUserOperations::test_create_user

# Run tests via tox (mirrors CI)
pip install tox
tox -e py
```

Test configuration is in `pyproject.toml` under `[tool.pytest.ini_options]`:
- `asyncio_mode = "auto"` — async tests run automatically
- Tests in `mlflow_oidc_auth/tests/integration/` are excluded by default (require a running server)
- Directories like `mlruns`, `htmlcov`, `__pycache__` are excluded from test discovery

### Frontend Tests (Vitest)

```bash
cd web-react

# Run all tests
yarn test

# Run with coverage
yarn test:coverage

# Run a specific test file
npx vitest run src/features/experiments/experiments-page.test.tsx
```

Test configuration is in `vite.config.ts`:
- Environment: `jsdom`
- Coverage provider: `v8` with `lcov` reporter
- Coverage thresholds: 80% for statements, branches, functions, and lines
- Setup file: `src/tests/setup.tsx`

### Integration Tests (Playwright)

Integration tests require a running mlflow-oidc-auth instance:

```bash
# Install Playwright browsers
python -m playwright install chromium

# Run against a local instance
tox -e integration

# Run against an already-running instance
export MLFLOW_OIDC_E2E_BASE_URL=http://localhost:8080
tox -e integration-live
```

## Code Style and Formatting

### Python

- **Formatter:** [Black](https://github.com/psf/black) with line length 160
  ```bash
  black mlflow_oidc_auth/
  ```
- **Unused imports:** [autoflake](https://github.com/PyCQA/autoflake) (available as dev dependency)
  ```bash
  autoflake --in-place --remove-all-unused-imports mlflow_oidc_auth/
  ```
- **Security analysis:** [Bandit](https://github.com/PyCQA/bandit) (run in CI on `mlflow_oidc_auth/**` paths)

### Frontend (TypeScript/React)

- **Formatter:** [Prettier](https://prettier.io/) — semi, tabWidth 2, printWidth 80, trailing commas
  ```bash
  cd web-react
  yarn format
  ```
- **Linter:** [ESLint](https://eslint.org/) with TypeScript, React hooks, React DOM, and Prettier integration
  ```bash
  cd web-react
  yarn lint
  ```
- **Type checking:** TypeScript in strict mode
  ```bash
  cd web-react
  npx tsc -b
  ```

### Pre-commit Hooks

The project uses [pre-commit](https://pre-commit.com/) for automated checks before each commit:

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

Configured hooks (`.pre-commit-config.yaml`):
- `check-yaml` — validates YAML files
- `check-added-large-files` — blocks files >800KB
- `detect-private-key` — prevents accidental key commits
- `end-of-file-fixer` — ensures files end with newline
- `trailing-whitespace` — removes trailing whitespace
- `mixed-line-ending` — normalizes line endings
- `check-toml` — validates TOML files
- `black` — Python code formatting

## Database Migrations

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/). Migrations run automatically on application startup in `create_app()`.

### Creating a New Migration

```bash
# Auto-generate a migration from model changes
cd mlflow_oidc_auth/db
alembic revision --autogenerate -m "description of change"
```

Migration scripts live in `mlflow_oidc_auth/db/migrations/versions/`.

### SQLAlchemy Models

ORM models are in `mlflow_oidc_auth/db/models/` and follow these conventions:
- Prefixed with `Sql`: `SqlUser`, `SqlExperimentPermission`, `SqlGroup`
- Inherit from `Base` (declarative base in `_base.py`)
- Use `Mapped[T]` type annotations for columns

## Git Conventions

### Commit Messages

The project uses [Conventional Commits](https://www.conventionalcommits.org/), enforced by CI:

```
<type>(<optional scope>): <description>
```

- **Types:** `feat`, `fix`, `chore`, `docs`, `style`, `ci`, `refactor`, `perf`, `test`, `build`
- Subject must **not** start with an uppercase letter
- Scope is optional: `feat(auth): add token refresh`

Examples:
```
feat: add workspace permission management
fix(ui): update module-level workspace state synchronously
docs: update installation guide for v1.1
refactor(hooks): simplify permission resolution
test: add coverage for regex permission matching
```

### Pull Requests

PR titles must follow the same Conventional Commits format (validated by `pr-validate-title.yml`).

### Branches

- `main` — production releases
- `rc` — release candidate (pre-release channel)

### Releases

Automated via [semantic-release](https://github.com/semantic-release/semantic-release) on push to `main`:
1. Analyzes commit messages to determine version bump
2. Runs `scripts/release.sh` for version bumping
3. Builds the React frontend (`vite build` → `mlflow_oidc_auth/ui/`)
4. Publishes to PyPI

## CI/CD Pipeline

The following GitHub Actions workflows run on pull requests and pushes:

| Workflow | File | Trigger | What it does |
|----------|------|---------|--------------|
| **Unit Tests** | `unit-tests.yml` | PR + push to main | Runs frontend tests (Vitest) and backend tests (tox/pytest), uploads coverage to SonarCloud |
| **Pre-commit** | `pre-commit.yml` | PR + push | Runs all pre-commit hooks |
| **Bandit** | `bandit.yml` | PR + push | Security analysis on Python code |
| **PR Title** | `pr-validate-title.yml` | PR | Validates Conventional Commits format |
| **Commit Message** | `commit-message-check.yml` | PR + push | Validates commit message format |
| **PyPI Publish** | `pypi.yml` | Push to main | Builds and publishes to PyPI via semantic-release |
| **PyPI Test** | `pypi-test.yml` | Manual/RC | Publishes to Test PyPI |

## Contribution

Any contribution is always welcome. We seek help with:

- **Testing** — unit tests, integration tests, edge cases
- **Documentation** — improvements, examples, corrections
- **Bug reports** — with reproduction steps
- **Feature requests** — with use cases
- **Showcases** — success stories and deployment patterns

### How to Contribute

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes following the code style guidelines above
4. Add or update tests for your changes
5. Ensure all tests pass (`pytest` for backend, `yarn test` for frontend)
6. Ensure code formatting is correct (`black` for Python, `yarn format` for frontend)
7. Commit with a Conventional Commits message
8. Open a pull request with a descriptive title (Conventional Commits format)

### Optional Dependencies for Development

```bash
# Install all optional dependencies for full development
pip install -e ".[dev,test,cloud]"

# Or specific cloud providers
pip install -e ".[dev,test,aws]"
pip install -e ".[dev,test,azure]"
pip install -e ".[dev,test,vault]"
```

### Redis (for Cache Testing)

A Docker Compose file is available for testing Redis cache integration:

```bash
cd scripts
docker compose up -d
```
