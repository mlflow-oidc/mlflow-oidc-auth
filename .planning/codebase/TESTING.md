# Testing Patterns

**Analysis Date:** 2026-03-23

## Test Frameworks

### Python

**Runner:**
- **pytest** (v8.x) with **pytest-asyncio** for async test support
- **pytest-cov** for coverage
- Config: `pyproject.toml` `[tool.pytest.ini_options]`
- `asyncio_mode = "auto"` - async tests run automatically without `@pytest.mark.asyncio`

**Assertion Library:**
- pytest native `assert` (primary, used in class-based and function-based tests)
- `unittest.TestCase` assertions (`self.assertEqual`, `self.assertTrue`, etc.) in older tests

**Coverage:**
- **coverage.py** (via tox) and **pytest-cov**
- Config: `.coveragerc` and `tox.ini` `[coverage:run]`
- Source: `mlflow_oidc_auth/`
- Branch coverage: enabled
- Omits: `mlflow_oidc_auth/tests/*`, `mlflow_oidc_auth/db/migrations/versions/*`, `mlflow_oidc_auth/views/*`

**Run Commands:**
```bash
# Unit tests via tox (CI default)
tox -e py

# Unit tests directly with pytest
pytest -s -m "not integration" mlflow_oidc_auth/tests

# With coverage
coverage run -m pytest -s -m "not integration" mlflow_oidc_auth/tests
coverage xml

# Integration tests (requires running server + Playwright)
tox -e integration

# Integration tests against live server
tox -e integration-live
```

### React/TypeScript

**Runner:**
- **Vitest** (v4.x) with jsdom environment
- Config: `web-react/vite.config.ts` `test` section
- Setup file: `web-react/src/tests/setup.tsx`
- Globals enabled (`globals: true`) - `describe`, `it`, `expect` available without imports

**Assertion Library:**
- Vitest built-in `expect()`
- `@testing-library/jest-dom` matchers (e.g., `toBeInTheDocument()`, `toHaveAttribute()`, `toHaveClass()`)

**Coverage:**
- **v8** provider (via `@vitest/coverage-v8`)
- Reporter: `lcov` (output to `web-react/coverage/`)
- Include: `src/**/*.{ts,tsx}`
- Exclude: `src/tests/**`, `**/*.d.ts`
- **Thresholds enforced:**
  - Statements: 80%
  - Branches: 80%
  - Functions: 80%
  - Lines: 80%

**Run Commands:**
```bash
# Run all React tests
cd web-react && yarn test

# Run with coverage (used in CI)
cd web-react && yarn test:coverage

# Lint
cd web-react && yarn lint

# Format
cd web-react && yarn format
```

## Test File Organization

### Python Tests

**Location:** `mlflow_oidc_auth/tests/` (separate from source, configured in `pyproject.toml` `testpaths`)

**Naming:** `test_<module_name>.py`

**Structure:**
```
mlflow_oidc_auth/tests/
├── __init__.py
├── test_app.py                    # Tests for app.py
├── test_auth.py                   # Tests for auth.py
├── test_auth_module.py            # Extended auth module tests
├── test_config.py                 # Tests for config.py
├── test_config_providers.py       # Tests for config providers
├── test_db_models.py              # Tests for DB ORM models
├── test_db_utils.py               # Tests for DB utilities
├── test_dependencies.py           # Tests for dependencies.py (common)
├── test_dependencies_gateway.py   # Tests for gateway-specific dependencies
├── test_dependencies_nongateway.py # Tests for non-gateway dependencies
├── test_entities.py               # Tests for entity classes
├── test_exceptions.py             # Tests for exception handling
├── test_logger.py                 # Tests for logger module
├── test_oauth.py                  # Tests for OAuth module
├── test_permissions.py            # Tests for permission system
├── test_sqlalchemy_store.py       # Tests for SQLAlchemy store (core)
├── test_sqlalchemy_store_gateway.py  # Tests for gateway-specific store ops
├── test_sqlalchemy_store_scorer.py   # Tests for scorer-specific store ops
├── test_user.py                   # Tests for user module
├── test_webhook_model.py          # Tests for webhook model
├── test_webhook_router.py         # Tests for webhook router
├── bridge/
│   └── test_user.py               # Tests for bridge/user module
├── db/
│   └── test_cli.py                # Tests for DB CLI commands
├── graphql/
│   ├── test_graphql_middleware.py  # Tests for GraphQL middleware
│   └── test_graphql_patch.py      # Tests for GraphQL patches
├── hooks/
│   ├── test_after_request.py      # Tests for Flask after-request hooks
│   └── test_before_request.py     # Tests for Flask before-request hooks
├── middleware/
│   ├── conftest.py                # Middleware test fixtures
│   ├── test_auth_middleware.py     # Tests for auth middleware
│   └── test_auth_aware_wsgi_middleware.py  # Tests for WSGI middleware
├── plugins/
│   ├── test_plugin_system.py      # Tests for plugin system
│   └── test_group_detection_microsoft_entra_id.py  # Entra ID plugin tests
├── repository/
│   ├── test_experiment_permission.py
│   ├── test_experiment_permission_group.py
│   ├── test_experiment_permission_regex.py
│   ├── test_experiment_permission_regex_group.py
│   ├── test_gateway_endpoint_group_permissions.py
│   ├── test_gateway_endpoint_group_regex_permissions.py
│   ├── test_gateway_endpoint_permissions.py
│   ├── test_gateway_endpoint_regex_permissions.py
│   ├── test_group.py
│   ├── test_prompt_permission_group.py
│   ├── test_registered_model_permission.py
│   ├── test_registered_model_permission_group.py
│   ├── test_registered_model_permission_regex.py
│   ├── test_registered_model_permission_regex_group.py
│   ├── test_user_repository.py
│   ├── test_user_repository_delete_with_permissions.py
│   └── test_utils.py
├── responses/
│   └── test_client_error.py       # Tests for Flask error responses
├── routers/
│   ├── conftest.py                # Router test fixtures (comprehensive)
│   ├── shared_fixtures.py         # Shared fixtures for router tests
│   ├── test_auth.py
│   ├── test_experiment_permissions.py
│   ├── test_gateway_endpoint_permissions.py
│   ├── test_gateway_model_definition_permissions.py
│   ├── test_gateway_secret_permissions.py
│   ├── test_group_permissions_gateway.py
│   ├── test_group_permissions_nongateway.py
│   ├── test_health.py
│   ├── test_prompt_permissions.py
│   ├── test_registered_model_permissions.py (via test_registered_model_permissions)
│   ├── test_scorer_permissions.py
│   ├── test_trash.py
│   ├── test_ui.py
│   ├── test_user_group_scorer_permissions.py
│   ├── test_user_permissions.py
│   ├── test_user_permissions_gateway.py
│   ├── test_user_permissions_nongateway.py
│   └── test_users.py
├── utils/
│   ├── test_batch_permissions.py
│   ├── test_batch_permissions_gateway.py
│   ├── test_data_fetching.py
│   ├── test_data_fetching_gateway.py
│   ├── test_permissions_gateway.py
│   ├── test_request_helpers.py
│   ├── test_request_helpers_fastapi.py
│   └── test_uri_helpers.py
├── validators/
│   ├── test_experiment.py
│   ├── test_gateway.py
│   ├── test_registered_model.py
│   ├── test_run.py
│   ├── test_run_validator.py
│   └── test_stuff.py
├── session/
│   └── __init__.py
└── integration/
    ├── conftest.py                # Integration test fixtures (session-scoped)
    ├── users.py                   # Test user definitions
    ├── utils.py                   # Integration test utilities
    ├── test_authentication.py
    ├── test_access_tokens.py
    ├── test_admin_capabilities.py
    ├── test_e2e_permissions_workflow.py
    ├── test_group_permissions.py
    ├── test_permission_enforcement.py
    ├── test_populate_test_data.py
    ├── test_populate_users.py
    ├── test_resource_creation.py
    ├── test_scorers_permissions.py
    └── test_token_scorer_seeding.py
```

**Total:** ~107 Python test files (including integration)

### React Tests

**Location:** Co-located with source files (same directory as component/module)

**Naming:** `<module-name>.test.tsx` or `<module-name>.test.ts`

**Structure:**
```
web-react/src/
├── app.test.tsx                    # App routing tests
├── main.test.tsx                   # Entry point tests
├── tests/
│   └── setup.tsx                   # Test setup (jest-dom, dialog polyfill)
├── core/
│   ├── components/
│   │   ├── main-layout.test.tsx
│   │   ├── access-token-modal.test.tsx
│   │   └── create-access-token-button.test.tsx
│   ├── configs/
│   │   └── api-endpoints.test.ts
│   ├── context/
│   │   └── user-provider.test.tsx
│   ├── hooks/
│   │   ├── use-api.test.tsx
│   │   ├── use-auth.test.ts
│   │   ├── use-data-hooks.test.tsx
│   │   ├── use-entity-permissions.test.tsx
│   │   ├── use-gateway-data-hooks.test.tsx
│   │   ├── use-gateway-permissions.test.tsx
│   │   ├── use-search.test.ts
│   │   ├── use-update-webhook.test.tsx
│   │   ├── use-user.test.tsx
│   │   └── use-webhooks.test.ts
│   └── services/
│       ├── api-utils.test.ts
│       ├── create-api-fetcher.test.ts
│       ├── entity-service.test.ts
│       ├── gateway-service.test.ts
│       ├── http.test.ts
│       ├── trash-service.test.ts
│       ├── user-service.test.ts
│       └── webhook-service.test.ts
├── features/
│   ├── ai-gateway/
│   │   ├── ai-endpoints-page.test.tsx
│   │   ├── ai-endpoints-permission-page.test.tsx
│   │   ├── ai-models-page.test.tsx
│   │   ├── ai-models-permissions-page.test.tsx
│   │   ├── ai-secrets-page.test.tsx
│   │   └── ai-secrets-permissions-page.test.tsx
│   ├── auth/
│   │   ├── auth-page.test.tsx
│   │   ├── components/
│   │   │   ├── protected-route.test.tsx
│   │   │   └── redirect-if-auth.test.tsx
│   │   ├── hooks/
│   │   │   └── use-auth-errors.test.ts
│   │   └── services/
│   │       └── auth-service.test.ts
│   ├── [... other features with co-located tests]
│   └── permissions/
│       ├── components/
│       │   ├── add-regex-rule-modal.test.tsx
│       │   ├── entity-permissions-manager.test.tsx
│       │   ├── entity-permissions-page-layout.test.tsx
│       │   ├── grant-permission-modal.test.tsx
│       │   ├── normal-permissions-view.test.tsx
│       │   └── regex-permissions-view.test.tsx
│       ├── utils/
│       │   └── permission-utils.test.ts
│       └── shared-permissions-page.test.tsx
└── shared/
    ├── components/
    │   ├── button.test.tsx
    │   ├── loading-spinner.test.tsx
    │   ├── modal.test.tsx
    │   ├── [... ~20 more component tests]
    │   └── toast/
    │       ├── toast.test.tsx
    │       ├── toast-context.test.tsx
    │       └── use-toast.test.tsx
    ├── context/
    │   ├── runtime-config-provider.test.tsx
    │   └── use-runtime-config.test.tsx
    ├── services/
    │   └── runtime-config.test.ts
    └── utils/
        ├── theme-utils.test.ts
        └── string-utils.test.ts
```

**Total:** ~102 React test files

## Test Structure Patterns

### Python - pytest class-based (unittest-style)

Used for configuration and exception tests:
```python
class TestAppConfig(unittest.TestCase):
    """Test the AppConfig class initialization and configuration loading."""

    def setUp(self):
        """Set up test environment."""
        self.original_env = dict(os.environ)

    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_app_config_default_values(self):
        """Test that AppConfig initializes with correct default values."""
        config = AppConfig()
        self.assertEqual(config.DEFAULT_MLFLOW_PERMISSION, "MANAGE")
```

### Python - pytest class-based (modern)

Used for auth, middleware, and router tests:
```python
class TestAuth:
    @patch("mlflow_oidc_auth.auth.requests")
    @patch("mlflow_oidc_auth.auth.config")
    def test_get_oidc_jwks_success(self, mock_config, mock_requests):
        """Test successful JWKS retrieval from OIDC provider"""
        mock_config.OIDC_DISCOVERY_URL = "https://example.com/.well-known/openid_configuration"
        # ...
        assert result == expected
```

### Python - pytest function-based

Used for validator, repository, and entity tests:
```python
@pytest.fixture
def repo(session_maker):
    return ExperimentPermissionRepository(session_maker)

def test_grant_permission_success(repo, session):
    """Test successful grant_permission to cover line 62"""
    user = MagicMock(id=2)
    # ...
    result = repo.grant_permission("exp2", "user", "READ")
    assert result is not None
```

### React - Vitest describe/it pattern

```typescript
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

describe("AuthPage", () => {
  beforeEach(() => {
    mockUseRuntimeConfig.mockReturnValue({
      provider: "Sign in with OIDC",
      basePath: "/api",
      uiPath: "/ui",
      authenticated: false,
      gen_ai_gateway_enabled: false,
    });
  });

  it("renders sign in button with correct link", () => {
    render(<AuthPage />);
    const button = screen.getByText("Sign in with OIDC");
    expect(button).toBeInTheDocument();
  });
});
```

## Mocking Patterns

### Python - unittest.mock

**Primary mocking tool:** `unittest.mock` (`patch`, `MagicMock`, `AsyncMock`)

**Patching module-level imports:**
```python
from unittest.mock import MagicMock, patch

@patch("mlflow_oidc_auth.auth.requests")
@patch("mlflow_oidc_auth.auth.config")
def test_get_oidc_jwks_success(self, mock_config, mock_requests):
    mock_config.OIDC_DISCOVERY_URL = "https://example.com/..."
    mock_requests.get.return_value = MagicMock(json=lambda: {...})
```

**Patching with context managers:**
```python
with patch("mlflow_oidc_auth.validators.experiment.get_experiment_id", return_value="123"):
    perm = experiment._get_permission_from_experiment_id("alice")
    assert perm.can_read is True
```

**Environment variable mocking:**
```python
with patch.dict(os.environ, {"TEST_BOOL": "true"}):
    result = get_bool_env_variable("TEST_BOOL", False)
```

**AsyncMock for async dependencies:**
```python
from unittest.mock import AsyncMock

oidc_mock.authorize_redirect = AsyncMock(
    return_value=MagicMock(status_code=302, headers={"Location": "https://provider.com/auth"})
)
```

**Store/repository mocking in router tests:**

Router tests use an extensive autouse fixture (`_patch_router_stores`) in `mlflow_oidc_auth/tests/routers/conftest.py` that patches the `store` object across all router modules simultaneously:
```python
@pytest.fixture(autouse=True)
def _patch_router_stores(mock_store):
    patches = [
        patch("mlflow_oidc_auth.store.store", mock_store),
        patch("mlflow_oidc_auth.routers.experiment_permissions.store", mock_store),
        patch("mlflow_oidc_auth.routers.user_permissions.store", mock_store),
        # ... many more patches
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()
```

**Test data helpers:**
```python
def create_test_user(username="testuser", display_name="Test User", is_admin=False):
    """Helper function to create test User entities with correct constructor"""
    return User(id_=1, username=username, password_hash="hashed_password", ...)
```

### React - Vitest mocking

**Module mocking with `vi.mock()`:**
```typescript
vi.mock("../../shared/context/use-runtime-config", () => ({
  useRuntimeConfig: () => mockUseRuntimeConfig(),
}));

vi.mock("./hooks/use-auth-errors", () => ({
  useAuthErrors: () => mockUseAuthErrors(),
}));
```

**Component mocking for lazy-loaded routes:**
```typescript
vi.mock("./features/auth/auth-page", () => ({
  default: () => <div>AuthPage</div>,
}));
```

**Global fetch mocking:**
```typescript
globalThis.fetch = vi.fn<typeof fetch>();

vi.mocked(fetch).mockResolvedValue({
  ok: true,
  status: 200,
  headers: new Headers({ "content-type": "application/json" }),
  json: () => Promise.resolve({ data: "test" }),
} as Response);
```

**Typed mock functions:**
```typescript
const mockUseAuthErrors: Mock<() => string[]> = vi.fn();
```

## Fixtures

### Python - pytest fixtures

**Test database fixtures** (`mlflow_oidc_auth/tests/routers/conftest.py`):
```python
@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    db_fd, db_path = tempfile.mkstemp()
    yield db_path
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def test_engine(temp_db):
    engine = create_engine(f"sqlite:///{temp_db}", echo=False)
    Base.metadata.create_all(engine)
    return engine
```

**In-memory SQLite for store tests** (`mlflow_oidc_auth/tests/test_sqlalchemy_store.py`):
```python
@pytest.fixture
@patch("mlflow_oidc_auth.sqlalchemy_store.dbutils.migrate_if_needed")
def store(_mock_migrate_if_needed):
    store = SqlAlchemyStore()
    store.init_db("sqlite:///:memory:")
    return store
```

**Mock store with all repos mocked:**
```python
@pytest.fixture
def mock_store():
    store = SqlAlchemyStore()
    store.user_repo = MagicMock()
    store.experiment_repo = MagicMock()
    store.group_repo = MagicMock()
    # ... all repos mocked
    return store
```

**FastAPI test client fixtures:**
```python
@pytest.fixture
def test_app(mock_store, mock_oauth, mock_config, mock_tracking_store, mock_permissions):
    """Create a test FastAPI application with all routers."""
    # ... extensive patching, builds FastAPI app, yields it

@pytest.fixture
def client(test_app):
    return TestClientWrapper(TestClient(test_app))

@pytest.fixture
def authenticated_client(test_app, authenticated_session):
    client = TestClient(test_app)
    client.headers["Authorization"] = "Basic " + base64.b64encode(b"user@example.com:password").decode()
    return TestClientWrapper(client)
```

**TestClientWrapper** (`mlflow_oidc_auth/tests/routers/conftest.py`):
Custom wrapper around `TestClient` that handles `data` kwarg for DELETE requests and maps `allow_redirects` to `follow_redirects` for compatibility.

### React - Vitest setup

**Test setup** (`web-react/src/tests/setup.tsx`):
```typescript
import "@testing-library/jest-dom";
import { vi, beforeAll } from "vitest";

beforeAll(() => {
  // Polyfill dialog methods not supported in jsdom
  HTMLDialogElement.prototype.showModal = vi.fn(function(this: HTMLDialogElement) {
    this.open = true;
  });
  HTMLDialogElement.prototype.close = vi.fn(function(this: HTMLDialogElement) {
    this.open = false;
  });
});
```

## Test Types

### Unit Tests (Python)

- **Scope:** Test individual functions, classes, and methods in isolation
- **Location:** `mlflow_oidc_auth/tests/` (non-integration subdirectories)
- **Marker:** Default (no marker required); integration tests are excluded with `-m "not integration"`
- **Dependencies:** All external calls mocked via `unittest.mock`
- **Database:** In-memory SQLite (`sqlite:///:memory:`) or mocked entirely
- **Approximately 90+ test files**

### Unit Tests (React)

- **Scope:** Test individual components, hooks, services, and utilities
- **Location:** Co-located with source files
- **Dependencies:** External modules mocked via `vi.mock()`
- **DOM:** jsdom environment
- **Approximately 102 test files**

### Integration Tests (Python)

- **Scope:** End-to-end tests against a running mlflow-oidc-auth server
- **Location:** `mlflow_oidc_auth/tests/integration/`
- **Marker:** `@pytest.mark.integration`
- **Run with:** `tox -e integration` or `tox -e integration-live`
- **Dependencies:**
  - Running mlflow-oidc-auth server (configurable via `MLFLOW_OIDC_E2E_BASE_URL`)
  - **Playwright** (Chromium) for browser-based tests
  - **httpx** for API-level tests
- **Excluded from default test run** via `norecursedirs = ["integration"]` in `pyproject.toml`
- **Session-scoped fixtures** for server health check, admin/user HTTP clients
- **Skip or fail behavior** configurable via `MLFLOW_OIDC_E2E_REQUIRE` env var

### E2E Tests (React)

- Excluded via `exclude: [...configDefaults.exclude, "e2e/*"]` in vite config
- No e2e directory currently exists in `web-react/src/`

## SonarCloud Integration

**Config:** `sonar-project.properties`

- **Organization:** `mlflow-oidc`
- **Python coverage:** `coverage.xml`
- **TypeScript coverage:** `web-react/coverage/lcov.info`
- **Source dirs:** `mlflow_oidc_auth`, `web-react/src`
- **Test patterns:** `**/test_*.py`, `**/tests/**/*.py`, `**/*.test.tsx`, `**/*.test.ts`
- **Exclusions from analysis:** `node_modules`, `dist`, `__pycache__`, `migrations`
- **Exclusions from coverage:** test files, migration versions, `vite.config.ts`, `setup.tsx`
- **Exclusions from duplication detection:** test files
- **Suppressed security rules in test files:**
  - `S2068` (hardcoded credentials) - Python & TypeScript
  - `S6418` (hardcoded secrets) - Python & TypeScript
  - `S4502` (CSRF) - Python & TypeScript
  - `S5332` (clear-text protocols) - Python & TypeScript
  - `S5443` (publicly accessible storage) - Python & TypeScript

## CI Testing Pipeline

Defined in `.github/workflows/unit-tests.yml`:

1. **React tests:** `yarn test:coverage` (Vitest with v8 coverage, 80% thresholds)
2. **Python tests:** `tox -e py` (pytest + coverage, generates `coverage.xml`)
3. **SonarCloud scan:** Uploads both Python and React coverage reports
4. Runs on: pull requests (opened, edited, reopened, synchronize) and pushes to `main`

Additional CI checks:
- `.github/workflows/pre-commit.yml` - Runs all pre-commit hooks
- `.github/workflows/bandit.yml` - Security analysis on `mlflow_oidc_auth/**` changes
- `.github/workflows/commit-message-check.yml` - Conventional commit validation
- `.github/workflows/pr-validate-title.yml` - Semantic PR title validation

## Test Gaps

**Areas with no or minimal test coverage:**

1. **`mlflow_oidc_auth/views/`** - Explicitly omitted from coverage (`views/*` in `.coveragerc`), no test files found
2. **`mlflow_oidc_auth/db/migrations/versions/`** - Explicitly excluded from coverage (migration scripts)
3. **`mlflow_oidc_auth/hack.py` and `mlflow_oidc_auth/hack/`** - Only one test file (`test_hack.py`); the hack module injects HTML into MLflow UI
4. **React E2E tests** - Excluded in vite config but no `e2e/` directory exists in `web-react`
5. **Config providers (cloud)** - `config_providers/` has `test_config_providers.py` but cloud providers (AWS, Azure, Vault, K8s) require external services
6. **GraphQL** - Only 2 test files (`test_graphql_middleware.py`, `test_graphql_patch.py`) for the GraphQL authorization middleware
7. **`mlflow_oidc_auth/oauth.py`** - Only `test_oauth.py` exists; OIDC flows are complex and hard to fully test in unit tests
8. **Integration tests are excluded from CI by default** - Only run via `tox -e integration` (requires running server), not in the standard `unit-tests.yml` workflow

---

*Testing analysis: 2026-03-23*
