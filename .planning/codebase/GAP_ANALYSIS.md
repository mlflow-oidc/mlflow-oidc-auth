# Gap Analysis: mlflow-oidc-auth vs Upstream MLflow 3.10.1 Auth

> Generated 2026-03-27 by comparing `mlflow/server/auth/__init__.py` (3438 lines)
> and `mlflow/server/fastapi_app.py` from MLflow 3.10.1 against our plugin.

## Executive Summary

Our plugin (`mlflow-oidc-auth`) has **strong security coverage** for Flask/protobuf-based MLflow API routes, with some areas where we exceed upstream capabilities (group permissions, regex permissions, OIDC). However, there are **three critical architectural gaps** and several **missing security controls** related to MLflow 3.x features that bypass Flask entirely.

### Severity Legend
- **CRITICAL** — Security gap; requests bypass auth entirely
- **HIGH** — Missing feature parity; functionality not working
- **MEDIUM** — Missing but has workarounds or lower impact
- **LOW** — Nice-to-have parity; cosmetic or edge case

---

## 1. Architecture Gaps

### GAP-ARCH-01: FastAPI-native routes not authenticated — RESOLVED ✅

> **Resolved in commit `d74a5bf`** — Phase 1 implementation.

**Resolution:** Implemented Option B — our `create_app()` now calls `_include_mlflow_fastapi_routers()` which dynamically imports and registers the 4 upstream FastAPI routers (`otel_router`, `gateway_router`, `assistant_router`, `job_api_router`) with try/except per-router for forward compatibility. Added `FastAPIPermissionMiddleware` in `mlflow_oidc_auth/middleware/fastapi_permission_middleware.py` (238 lines) that provides OIDC-aware permission enforcement for all FastAPI-native routes. 45 tests added.

### GAP-ARCH-02: Upstream uses `_MLFLOW_SGI_NAME` gating (MEDIUM)

**What upstream does:**
In `create_app()`, line 3433:
```python
if _MLFLOW_SGI_NAME.get() == "uvicorn":
    fastapi_app = create_fastapi_app(app)
    add_fastapi_permission_middleware(fastapi_app)
    return fastapi_app
else:
    return app
```

**What our plugin does:**
We always return a FastAPI app. This is fine — our plugin is designed for ASGI/FastAPI. No action needed.

### GAP-ARCH-03: Auth context bridge differences (LOW)

**Upstream** authenticates in Flask's `_before_request` via `authenticate_request()` and for FastAPI routes via `_authenticate_fastapi_request()` (Basic Auth only).

**Our plugin** authenticates in FastAPI's `AuthMiddleware` (OIDC, JWT, Basic, Session) and passes context to Flask via ASGI scope → WSGI environ bridge. This is a **superior** approach that supports more auth methods. No gap here — just noting the difference.

---

## 2. Before-Request Handler Gaps (Security Controls)

### 2a. Protobuf-based handlers — PARITY ACHIEVED

| Proto Class | Upstream Validator | Our Validator | Status |
|---|---|---|---|
| **Experiments** | | | |
| GetExperiment | `validate_can_read_experiment` | `validate_can_read_experiment` | MATCH |
| GetExperimentByName | `validate_can_read_experiment` | `validate_can_read_experiment_by_name` | MATCH (different name, same intent) |
| DeleteExperiment | `validate_can_delete_experiment` | `validate_can_delete_experiment` | MATCH |
| RestoreExperiment | `validate_can_delete_experiment` | `validate_can_delete_experiment` | MATCH |
| UpdateExperiment | `validate_can_update_experiment` | `validate_can_update_experiment` | MATCH |
| SetExperimentTag | `validate_can_update_experiment` | `validate_can_update_experiment` | MATCH |
| DeleteExperimentTag | `validate_can_update_experiment` | `validate_can_update_experiment` | MATCH |
| **Runs** | | | |
| CreateRun | `validate_can_update_experiment` | `validate_can_update_experiment` | MATCH |
| GetRun | `validate_can_read_run` | `validate_can_read_run` | MATCH |
| DeleteRun | `validate_can_delete_run` | `validate_can_delete_run` | MATCH |
| RestoreRun | `validate_can_delete_run` | `validate_can_delete_run` | MATCH |
| UpdateRun | `validate_can_update_run` | `validate_can_update_run` | MATCH |
| LogMetric | `validate_can_update_run` | `validate_can_update_run` | MATCH |
| LogBatch | `validate_can_update_run` | `validate_can_update_run` | MATCH |
| LogModel | `validate_can_update_run` | `validate_can_update_run` | MATCH |
| SetTag | `validate_can_update_run` | `validate_can_update_run` | MATCH |
| DeleteTag | `validate_can_update_run` | `validate_can_update_run` | MATCH |
| LogParam | `validate_can_update_run` | `validate_can_update_run` | MATCH |
| GetMetricHistory | `validate_can_read_run` | `validate_can_read_run` | MATCH |
| ListArtifacts | `validate_can_read_run` | `validate_can_read_run` | MATCH |
| **Model Registry** | | | |
| GetRegisteredModel | `validate_can_read_registered_model` | `validate_can_read_registered_model` | MATCH |
| DeleteRegisteredModel | `validate_can_delete_registered_model` | `validate_can_delete_registered_model` | MATCH |
| UpdateRegisteredModel | `validate_can_update_registered_model` | `validate_can_update_registered_model` | MATCH |
| RenameRegisteredModel | `validate_can_update_registered_model` | `validate_can_update_registered_model` | MATCH |
| GetLatestVersions | `validate_can_read_registered_model` | `validate_can_read_registered_model` | MATCH |
| CreateModelVersion | `validate_can_update_registered_model` | `validate_can_update_registered_model` | MATCH |
| GetModelVersion | `validate_can_read_registered_model` | `validate_can_read_registered_model` | MATCH |
| DeleteModelVersion | `validate_can_delete_registered_model` | `validate_can_delete_registered_model` | MATCH |
| UpdateModelVersion | `validate_can_update_registered_model` | `validate_can_update_registered_model` | MATCH |
| TransitionModelVersionStage | `validate_can_update_registered_model` | `validate_can_update_registered_model` | MATCH |
| GetModelVersionDownloadUri | `validate_can_read_registered_model` | `validate_can_read_registered_model` | MATCH |
| SetRegisteredModelTag | `validate_can_update_registered_model` | `validate_can_update_registered_model` | MATCH |
| DeleteRegisteredModelTag | `validate_can_update_registered_model` | `validate_can_update_registered_model` | MATCH |
| SetModelVersionTag | `validate_can_update_registered_model` | `validate_can_update_registered_model` | MATCH |
| DeleteModelVersionTag | `validate_can_delete_registered_model` | `validate_can_delete_registered_model` | MATCH |
| SetRegisteredModelAlias | `validate_can_update_registered_model` | `validate_can_update_registered_model` | MATCH |
| DeleteRegisteredModelAlias | `validate_can_delete_registered_model` | `validate_can_delete_registered_model` | MATCH |
| GetModelVersionByAlias | `validate_can_read_registered_model` | `validate_can_read_registered_model` | MATCH |
| **Scorers** | | | |
| RegisterScorer | `validate_can_update_experiment` | `validate_can_update_experiment` | MATCH |
| ListScorers | `validate_can_read_experiment` | `validate_can_read_experiment` | MATCH |
| GetScorer | `validate_can_read_scorer` | `validate_can_read_scorer` | MATCH |
| DeleteScorer | `validate_can_delete_scorer` | `validate_can_delete_scorer` | MATCH |
| ListScorerVersions | `validate_can_read_scorer` | `validate_can_read_scorer` | MATCH |
| **Prompt Optimization Jobs** | | | |
| CreatePromptOptimizationJob | `validate_can_update_experiment` | `validate_can_update_experiment` | MATCH |
| GetPromptOptimizationJob | `validate_can_read_prompt_optimization_job` | `validate_can_read_prompt_optimization_job` | MATCH |
| SearchPromptOptimizationJobs | `validate_can_read_experiment` | `validate_can_read_experiment` | MATCH |
| DeletePromptOptimizationJob | `validate_can_delete_prompt_optimization_job` | `validate_can_delete_prompt_optimization_job` | MATCH |
| CancelPromptOptimizationJob | `validate_can_update_prompt_optimization_job` | `validate_can_update_prompt_optimization_job` | MATCH |
| **Gateway Endpoints** | | | |
| CreateGatewayEndpoint | `sender_is_admin` | `validate_can_create_gateway` | **STRICTER** (see NOTE-01) |
| GetGatewayEndpoint | `validate_can_read_gateway_endpoint` | `validate_can_read_gateway_endpoint` | MATCH |
| UpdateGatewayEndpoint | `validate_can_update_gateway_endpoint` | `validate_can_update_gateway_endpoint` | MATCH |
| DeleteGatewayEndpoint | `validate_can_delete_gateway_endpoint` | `validate_can_delete_gateway_endpoint` | MATCH |
| AttachModelToGatewayEndpoint | `validate_can_update_gateway_endpoint` | `validate_can_update_gateway_endpoint` | MATCH |
| DetachModelFromGatewayEndpoint | `validate_can_update_gateway_endpoint` | `validate_can_update_gateway_endpoint` | MATCH |
| CreateGatewayEndpointBinding | `validate_can_update_gateway_endpoint` | `validate_can_update_gateway_endpoint` | MATCH |
| DeleteGatewayEndpointBinding | `validate_can_update_gateway_endpoint` | `validate_can_update_gateway_endpoint` | MATCH |
| ListGatewayEndpointBindings | `validate_can_read_gateway_endpoint` | `validate_can_read_gateway_endpoint` | MATCH |
| SetGatewayEndpointTag | `validate_can_update_gateway_endpoint` | `validate_can_update_gateway_endpoint` | MATCH |
| DeleteGatewayEndpointTag | `validate_can_update_gateway_endpoint` | `validate_can_update_gateway_endpoint` | MATCH |
| **Gateway Secrets** | | | |
| CreateGatewaySecret | `sender_is_admin` | `validate_can_create_gateway` | **STRICTER** (see NOTE-01) |
| GetGatewaySecretInfo | `validate_can_read_gateway_secret` | `validate_can_read_gateway_secret` | MATCH |
| UpdateGatewaySecret | `validate_can_update_gateway_secret` | `validate_can_update_gateway_secret` | MATCH |
| DeleteGatewaySecret | `validate_can_delete_gateway_secret` | `validate_can_delete_gateway_secret` | MATCH |
| **Gateway Model Definitions** | | | |
| CreateGatewayModelDefinition | `sender_is_admin` | `validate_can_create_gateway` | **STRICTER** (see NOTE-01) |
| GetGatewayModelDefinition | `validate_can_read_gateway_model_definition` | `validate_can_read_gateway_model_definition` | MATCH |
| UpdateGatewayModelDefinition | `validate_can_update_gateway_model_definition` | `validate_can_update_gateway_model_definition` | MATCH |
| DeleteGatewayModelDefinition | `validate_can_delete_gateway_model_definition` | `validate_can_delete_gateway_model_definition` | MATCH |
| **Workspaces** | | | |
| CreateWorkspace | `sender_is_admin` | `validate_can_create_workspace` | MATCH (both admin-only) |
| GetWorkspace | `validate_can_view_workspace` | `validate_can_read_workspace` | MATCH |
| ListWorkspaces | `None` (no before-request) | `validate_can_list_workspaces` | **STRICTER** (we gate, upstream filters in after-request) |
| UpdateWorkspace | `sender_is_admin` | `validate_can_update_workspace` | MATCH |
| DeleteWorkspace | `sender_is_admin` | `validate_can_delete_workspace` | MATCH |
| **Logged Models** | | | |
| CreateLoggedModel | `validate_can_update_experiment` | `validate_can_update_experiment` | MATCH |
| GetLoggedModel | `validate_can_read_logged_model` | `validate_can_read_logged_model` | MATCH |
| DeleteLoggedModel | `validate_can_delete_logged_model` | `validate_can_delete_logged_model` | MATCH |
| FinalizeLoggedModel | `validate_can_update_logged_model` | `validate_can_update_logged_model` | MATCH |
| DeleteLoggedModelTag | `validate_can_delete_logged_model` | `validate_can_delete_logged_model` | MATCH |
| SetLoggedModelTags | `validate_can_update_logged_model` | `validate_can_update_logged_model` | MATCH |
| LogLoggedModelParamsRequest | `validate_can_update_logged_model` | `validate_can_update_logged_model` | MATCH |

### 2b. Missing protobuf handlers — RESOLVED ✅

> **Resolved in commit `02adb99`** — Phase 2 implementation. Forward-compatible `try/except ImportError` wrapper handles protos that may not exist yet in current MLflow.

| Proto Class | Upstream Validator | Our Status | Severity |
|---|---|---|---|
| CreateGatewayBudgetPolicy | `sender_is_admin` | `_deny_non_admin` (admin-only) | RESOLVED |
| UpdateGatewayBudgetPolicy | `sender_is_admin` | `_deny_non_admin` (admin-only) | RESOLVED |
| DeleteGatewayBudgetPolicy | `sender_is_admin` | `_deny_non_admin` (admin-only) | RESOLVED |

### 2c. Flask route handlers

| Route | Upstream Validator | Our Validator | Status |
|---|---|---|---|
| GET_ARTIFACT | `validate_can_read_run` | `validate_can_read_run_artifact` | MATCH |
| UPLOAD_ARTIFACT | `validate_can_update_run` | `validate_can_update_run_artifact` | MATCH |
| GET_MODEL_VERSION_ARTIFACT | `validate_can_read_registered_model` | `validate_can_read_model_version_artifact` | MATCH |
| GET_TRACE_ARTIFACT | `validate_can_read_trace` | `validate_can_read_trace_artifact` | MATCH |
| GET_METRIC_HISTORY_BULK | `validate_can_read_run` | `validate_can_read_metric_history_bulk` | MATCH |
| GET_METRIC_HISTORY_BULK_INTERVAL | `validate_can_read_run` | `validate_can_read_metric_history_bulk_interval` | MATCH |
| SEARCH_DATASETS | `validate_can_search_datasets` | `validate_can_search_datasets` | MATCH |
| CREATE_PROMPTLAB_RUN | `validate_can_create_promptlab_run` | `validate_can_create_promptlab_run` | MATCH |
| GATEWAY_PROXY (GET/POST) | `validate_gateway_proxy` | `validate_gateway_proxy` | MATCH |
| INVOKE_SCORER | `validate_gateway_proxy` | `validate_gateway_proxy` | RESOLVED ✅ (`02adb99`) |
| GATEWAY_SUPPORTED_PROVIDERS | `validate_gateway_proxy` | `validate_gateway_proxy` | RESOLVED ✅ (`02adb99`) |
| GATEWAY_SUPPORTED_MODELS | `validate_gateway_proxy` | `validate_gateway_proxy` | RESOLVED ✅ (`02adb99`) |
| GATEWAY_PROVIDER_CONFIG | `sender_is_admin` | `_deny_non_admin` (admin-only) | RESOLVED ✅ (`02adb99`) |
| GATEWAY_SECRETS_CONFIG | `sender_is_admin` | `_deny_non_admin` (admin-only) | RESOLVED ✅ (`02adb99`) |

### 2d. Webhook handlers — NO GAP (verified)

> **Verified during Phase 2 analysis.** Our plugin handles ALL webhook CRUD (create, get, list, update, delete, test) via the FastAPI router in `mlflow_oidc_auth/routers/webhook.py` with `Depends(check_admin_permission)` dependency injection. No Flask-level hooks needed — the FastAPI dependency already enforces admin-only access.

| Proto Class | Upstream Validator | Our Status | Severity |
|---|---|---|---|
| CreateWebhook | `sender_is_admin` | Handled via FastAPI `check_admin_permission` | NO GAP |
| GetWebhook | `sender_is_admin` | Handled via FastAPI `check_admin_permission` | NO GAP |
| ListWebhooks | `sender_is_admin` | Handled via FastAPI `check_admin_permission` | NO GAP |
| UpdateWebhook | `sender_is_admin` | Handled via FastAPI `check_admin_permission` | NO GAP |
| DeleteWebhook | `sender_is_admin` | Handled via FastAPI `check_admin_permission` | NO GAP |
| TestWebhook | `sender_is_admin` | Handled via FastAPI `check_admin_permission` | NO GAP |

### 2e. FastAPI-native route validators (NEW in 3.10) — RESOLVED ✅

> **Resolved in commit `d74a5bf`** — Phase 1 implementation. All FastAPI-native routes are now registered and protected by `FastAPIPermissionMiddleware`.

| Route Pattern | Upstream Validator | Our Status | Severity |
|---|---|---|---|
| `/gateway/{endpoint}/mlflow/invocations` | `_get_gateway_validator` (USE permission) | `FastAPIPermissionMiddleware` gateway validator | RESOLVED |
| `/gateway/openai/v1/chat/completions` | `_get_gateway_validator` (USE permission) | `FastAPIPermissionMiddleware` gateway validator | RESOLVED |
| `/gateway/openai/v1/embeddings` | `_get_gateway_validator` (USE permission) | `FastAPIPermissionMiddleware` gateway validator | RESOLVED |
| `/gateway/openai/v1/responses` | `_get_gateway_validator` (USE permission) | `FastAPIPermissionMiddleware` gateway validator | RESOLVED |
| `/gateway/anthropic/v1/messages` | `_get_gateway_validator` (USE permission) | `FastAPIPermissionMiddleware` gateway validator | RESOLVED |
| `/gateway/gemini/v1beta/models/*/generateContent` | `_get_gateway_validator` (USE permission) | `FastAPIPermissionMiddleware` gateway validator | RESOLVED |
| `/gateway/gemini/v1beta/models/*/streamGenerateContent` | `_get_gateway_validator` (USE permission) | `FastAPIPermissionMiddleware` gateway validator | RESOLVED |
| `/v1/traces` | `_get_otel_validator` (experiment update permission) | `FastAPIPermissionMiddleware` otel validator | RESOLVED |
| `/ajax-api/3.0/jobs/*` | `_get_require_authentication_validator` | `FastAPIPermissionMiddleware` auth-required | RESOLVED |
| `/ajax-api/3.0/mlflow/assistant/*` | `_get_require_authentication_validator` | `FastAPIPermissionMiddleware` auth-required | RESOLVED |

---

## 3. After-Request Handler Gaps

### 3a. Handlers we have that match upstream

| Proto Class | Handler | Status |
|---|---|---|
| CreateExperiment | auto-grant MANAGE | MATCH |
| CreateRegisteredModel | auto-grant MANAGE | MATCH |
| DeleteRegisteredModel | cascade delete permissions | MATCH (ours also does group perms) |
| SearchExperiments | filter unreadable | MATCH (ours also does workspace filtering) |
| SearchLoggedModels | filter unreadable | MATCH |
| SearchRegisteredModels | filter unreadable | MATCH (ours also does workspace filtering) |
| RenameRegisteredModel | rename permissions | MATCH (ours also renames group perms) |
| RegisterScorer | auto-grant MANAGE | MATCH |
| DeleteScorer | cascade delete | MATCH |
| CreateGatewayEndpoint | auto-grant MANAGE | MATCH |
| CreateGatewaySecret | auto-grant MANAGE | MATCH |
| CreateGatewayModelDefinition | auto-grant MANAGE | MATCH |
| DeleteGatewayEndpoint | cascade delete | MATCH |
| DeleteGatewaySecret | cascade delete | MATCH |
| DeleteGatewayModelDefinition | cascade delete | MATCH |
| ListWorkspaces | filter by permission | MATCH |
| DeleteWorkspace | cascade delete permissions | MATCH |
| CreateWorkspace | auto-grant MANAGE | MATCH |

### 3b. Handlers we have that upstream doesn't

| Proto Class | Handler | Notes |
|---|---|---|
| UpdateGatewayEndpoint | rename permissions | We propagate renames; upstream doesn't |
| ListGatewayEndpoints | filter by permission | We filter; upstream doesn't |
| ListGatewaySecretInfos | filter by permission | We filter; upstream doesn't |
| ListGatewayModelDefinitions | filter by permission | We filter; upstream doesn't |

### 3c. After-request handler we're missing — RESOLVED ✅

> **Resolved in commit `02adb99`** — Phase 2 implementation. Added `_filter_search_model_versions()` with pagination re-fetch and workspace filtering.

| Proto Class | Upstream Handler | Our Status | Severity |
|---|---|---|---|
| SearchModelVersions | filter unreadable model versions | `_filter_search_model_versions` | RESOLVED |

---

## 4. Specific Behavioral Gaps

### GAP-SEC-01: Prompt Optimization Job validators — RESOLVED ✅

> **Resolved in Phase 3.** Proto investigation confirmed that `GetPromptOptimizationJob`, `DeletePromptOptimizationJob`, and `CancelPromptOptimizationJob` carry only `job_id` (no `experiment_id`). Created new `mlflow_oidc_auth/validators/prompt_optimization_job.py` with job-level validators that resolve `job_id` → `get_job()` → `params.experiment_id` → experiment permission, matching upstream behavior.

### GAP-SEC-02: Gateway Budget Policies — RESOLVED ✅

> **Resolved in commit `02adb99`** — Added forward-compatible `try/except ImportError` handler. Budget policy protos are mapped to `_deny_non_admin` (admin-only). When MLflow ships the protos in a future version, they'll be automatically picked up.

### GAP-SEC-03: Internal Gateway Auth Token — NO GAP (verified)

> **Verified in Phase 3.** `_MLFLOW_INTERNAL_GATEWAY_AUTH_TOKEN` does not exist in MLflow 3.10.1. This was a false positive in the original gap analysis. No action needed.

---

## 5. Capabilities We Exceed Upstream

Our plugin provides several features upstream does NOT have:

| Feature | Description |
|---|---|
| **OIDC Authentication** | Full OIDC/OAuth2 support with configurable providers |
| **JWT Bearer Token Auth** | Token-based authentication with JWKS validation |
| **Session-based Auth** | Cookie sessions via FastAPI SessionMiddleware |
| **Group Permissions** | Users can belong to groups, permissions cascade |
| **Regex Permissions** | Pattern-based permission rules (e.g., `experiments/team-*`) |
| **Group Regex Permissions** | Combined group + regex pattern permissions |
| **Gateway List Filtering** | We filter list results for endpoints/secrets/model definitions; upstream doesn't |
| **Gateway Rename Propagation** | We propagate endpoint renames to permission records |
| **Pluggable Config Providers** | AWS, Azure, Vault, K8s secrets integration |
| **Admin UI (React)** | Full management UI for permissions, users, groups |
| **Cache Backend Abstraction** | Pluggable cache with Redis support for multi-replica |

---

## 6. Recommended Remediation Priority

### Phase 1: Critical — Fix GAP-ARCH-01 (FastAPI-native routes) — COMPLETE ✅
> Resolved in commit `d74a5bf`. Registered upstream FastAPI routers with OIDC-aware permission middleware.

### Phase 2: High — Add missing security controls — COMPLETE ✅
> Resolved in commit `02adb99`. Added budget policy handlers, Flask route validators, SearchModelVersions filter, and verified webhook handling.

### Phase 3: Medium — Behavioral parity — COMPLETE ✅
> Resolved in Phase 3. Prompt optimization job validators now properly resolve `job_id` → experiment permission. Webhooks verified as handled via FastAPI router. `GATEWAY_SUPPORTED_PROVIDERS`/`GATEWAY_SUPPORTED_MODELS` done in Phase 2. Internal gateway auth token confirmed non-existent in MLflow 3.10.1.

---

## Notes

**NOTE-01:** Our gateway creation validators (`validate_can_create_gateway`) may be more flexible than upstream's `sender_is_admin`. Upstream requires admin for creating gateway endpoints/secrets/model definitions. Our validator may allow non-admin users with appropriate permissions. This is an intentional design choice, not a gap.

**NOTE-02:** The `ListLoggedModelArtifacts` handler exists in upstream's LOGGED_MODEL_BEFORE_REQUEST_HANDLERS but is NOT in our handlers. This needs investigation — check if this proto exists in MLflow 3.10.

**NOTE-03:** Upstream's `_find_validator()` also handles `GATEWAY_SUPPORTED_PROVIDERS`, `GATEWAY_SUPPORTED_MODELS`, `GATEWAY_PROVIDER_CONFIG`, `GATEWAY_SECRETS_CONFIG` via a separate Flask route mapping. These are discovery/config endpoints for the Gateway UI.
