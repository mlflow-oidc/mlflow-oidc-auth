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

### GAP-ARCH-01: FastAPI-native routes not authenticated (CRITICAL)

**What upstream does:**
MLflow 3.10 uses `create_fastapi_app()` (from `mlflow/server/fastapi_app.py`) which registers **four FastAPI routers BEFORE the Flask WSGI mount**:
- `otel_router` — OpenTelemetry trace ingestion (`/v1/traces`)
- `gateway_router` — AI Gateway invocation routes (`/gateway/{endpoint}/mlflow/invocations`, `/gateway/openai/v1/chat/completions`, etc.)
- `assistant_router` — AI assistant endpoints (`/ajax-api/3.0/mlflow/assistant/*`)
- `job_api_router` — Job API endpoints (`/ajax-api/3.0/jobs/*`)

Upstream then calls `add_fastapi_permission_middleware(fastapi_app)` which adds HTTP middleware that:
1. Finds a validator via `_find_fastapi_validator(path)`
2. Authenticates via Basic Auth (`_authenticate_fastapi_request`)
3. Allows admins full access
4. Runs async validators for gateway/otel/jobs/assistant routes

**What our plugin does:**
Our `create_app()` (in `mlflow_oidc_auth/app.py`) creates its own FastAPI app and mounts the **plain** `mlflow.server.app` Flask app via `AuthAwareWSGIMiddleware`. It never calls `create_fastapi_app()`, so:
- The 4 FastAPI-native routers **are never registered**
- Gateway invocations, OTel trace ingestion, assistant, and job API endpoints **do not exist**
- Even if MLflow registered them on the Flask side as fallback routes, they would go through our Flask `before_request_hook`, which has `validate_gateway_proxy` for the `/ajax-api/2.0/mlflow/gateway-proxy` path but NOT for the direct FastAPI gateway routes

**Impact:** Users cannot use AI Gateway invocations, OTel trace ingestion, assistant features, or Job API when running with the OIDC auth plugin. This is the bug reported in [Discussion #231](https://github.com/mlflow-oidc/mlflow-oidc-auth/discussions/231).

**Remediation options:**
1. **Option A (Recommended):** Call `create_fastapi_app(flask_app)` from upstream, then add our FastAPI middleware on top — effectively wrapping MLflow's FastAPI app with our OIDC auth
2. **Option B:** Register the 4 upstream routers ourselves and add our own permission middleware for them
3. **Option C:** Add `add_fastapi_permission_middleware()` equivalent to our FastAPI app + manually register the routers

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
| GetPromptOptimizationJob | `validate_can_read_prompt_optimization_job` | `validate_can_read_experiment` | **DIFFERS** (see GAP-SEC-01) |
| SearchPromptOptimizationJobs | `validate_can_read_experiment` | `validate_can_read_experiment` | MATCH |
| DeletePromptOptimizationJob | `validate_can_delete_prompt_optimization_job` | `validate_can_delete_experiment` | **DIFFERS** (see GAP-SEC-01) |
| CancelPromptOptimizationJob | `validate_can_update_prompt_optimization_job` | `validate_can_update_experiment` | **DIFFERS** (see GAP-SEC-01) |
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

### 2b. Missing protobuf handlers

| Proto Class | Upstream Validator | Our Status | Severity |
|---|---|---|---|
| CreateGatewayBudgetPolicy | `sender_is_admin` | **MISSING** | HIGH |
| UpdateGatewayBudgetPolicy | `sender_is_admin` | **MISSING** | HIGH |
| DeleteGatewayBudgetPolicy | `sender_is_admin` | **MISSING** | HIGH |

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
| INVOKE_SCORER | `validate_gateway_proxy` | **MISSING** | MEDIUM |
| GATEWAY_SUPPORTED_PROVIDERS | `validate_gateway_proxy` | **MISSING** | LOW |
| GATEWAY_SUPPORTED_MODELS | `validate_gateway_proxy` | **MISSING** | LOW |
| GATEWAY_PROVIDER_CONFIG | `sender_is_admin` | **MISSING** | MEDIUM |
| GATEWAY_SECRETS_CONFIG | `sender_is_admin` | **MISSING** | MEDIUM |

### 2d. Webhook handlers

| Proto Class | Upstream Validator | Our Status | Severity |
|---|---|---|---|
| CreateWebhook | `sender_is_admin` | **MISSING** | MEDIUM |
| GetWebhook | `sender_is_admin` | **MISSING** | MEDIUM |
| ListWebhooks | `sender_is_admin` | **MISSING** | MEDIUM |
| UpdateWebhook | `sender_is_admin` | **MISSING** | MEDIUM |
| DeleteWebhook | `sender_is_admin` | **MISSING** | MEDIUM |
| TestWebhook | `sender_is_admin` | **MISSING** | MEDIUM |

> NOTE: Our plugin has a separate webhook router in `mlflow_oidc_auth/routers/webhook.py` that may handle these via FastAPI dependency injection rather than Flask hooks. This needs verification.

### 2e. FastAPI-native route validators (NEW in 3.10)

| Route Pattern | Upstream Validator | Our Status | Severity |
|---|---|---|---|
| `/gateway/{endpoint}/mlflow/invocations` | `_get_gateway_validator` (USE permission) | **MISSING** (route doesn't exist) | CRITICAL |
| `/gateway/openai/v1/chat/completions` | `_get_gateway_validator` (USE permission) | **MISSING** | CRITICAL |
| `/gateway/openai/v1/embeddings` | `_get_gateway_validator` (USE permission) | **MISSING** | CRITICAL |
| `/gateway/openai/v1/responses` | `_get_gateway_validator` (USE permission) | **MISSING** | CRITICAL |
| `/gateway/anthropic/v1/messages` | `_get_gateway_validator` (USE permission) | **MISSING** | CRITICAL |
| `/gateway/gemini/v1beta/models/*/generateContent` | `_get_gateway_validator` (USE permission) | **MISSING** | CRITICAL |
| `/gateway/gemini/v1beta/models/*/streamGenerateContent` | `_get_gateway_validator` (USE permission) | **MISSING** | CRITICAL |
| `/v1/traces` | `_get_otel_validator` (experiment update permission) | **MISSING** | CRITICAL |
| `/ajax-api/3.0/jobs/*` | `_get_require_authentication_validator` | **MISSING** | HIGH |
| `/ajax-api/3.0/mlflow/assistant/*` | `_get_require_authentication_validator` | **MISSING** | HIGH |

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

### 3c. After-request handler we're missing

| Proto Class | Upstream Handler | Our Status | Severity |
|---|---|---|---|
| SearchModelVersions | filter unreadable model versions | **MISSING** | MEDIUM |

---

## 4. Specific Behavioral Gaps

### GAP-SEC-01: Prompt Optimization Job validators (MEDIUM)

**Upstream** has dedicated validators:
- `GetPromptOptimizationJob` → `validate_can_read_prompt_optimization_job` (resolves job → experiment)
- `DeletePromptOptimizationJob` → `validate_can_delete_prompt_optimization_job` (resolves job → experiment)
- `CancelPromptOptimizationJob` → `validate_can_update_prompt_optimization_job` (resolves job → experiment)

**Our plugin** uses experiment-level validators directly:
- `GetPromptOptimizationJob` → `validate_can_read_experiment`
- `DeletePromptOptimizationJob` → `validate_can_delete_experiment`
- `CancelPromptOptimizationJob` → `validate_can_update_experiment`

**Impact:** Our validators require the experiment_id to be directly available in the request. The upstream validators first resolve the job ID to an experiment ID. If the request only contains a job ID (not an experiment ID), our validators may fail. **This needs verification** — check what parameters the proto messages actually carry.

### GAP-SEC-02: Gateway Budget Policies (HIGH)

**Upstream** has 3 budget policy handlers, all gated to `sender_is_admin`:
- `CreateGatewayBudgetPolicy`
- `UpdateGatewayBudgetPolicy`
- `DeleteGatewayBudgetPolicy`

**Our plugin** doesn't import or handle these protos at all. If MLflow 3.10 ships with budget policy functionality, these endpoints are **unprotected** in our plugin — any authenticated user can create/modify/delete budget policies.

### GAP-SEC-03: Internal Gateway Auth Token (LOW)

**Upstream** has `_MLFLOW_INTERNAL_GATEWAY_AUTH_TOKEN` which allows server-spawned job subprocesses to authenticate without a real password on `/gateway/` routes only.

**Our plugin** doesn't implement this. Not a security gap (if anything, we're stricter), but it may cause internal MLflow processes to fail when they try to call gateway endpoints with the internal token.

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

### Phase 1: Critical — Fix GAP-ARCH-01 (FastAPI-native routes)
1. Integrate with `create_fastapi_app()` to register otel, gateway, assistant, job routers
2. Add OIDC-aware FastAPI permission middleware for these routes (equivalent to upstream's `add_fastapi_permission_middleware`)
3. This unblocks AI Gateway, OTel ingestion, assistant, and job features

### Phase 2: High — Add missing security controls
1. Add Gateway Budget Policy handlers (`CreateGatewayBudgetPolicy`, `UpdateGatewayBudgetPolicy`, `DeleteGatewayBudgetPolicy`) → admin-only
2. Add `INVOKE_SCORER` Flask route validator
3. Add `GATEWAY_PROVIDER_CONFIG` and `GATEWAY_SECRETS_CONFIG` admin-only validators
4. Add `SearchModelVersions` after-request filter

### Phase 3: Medium — Behavioral parity
1. Verify and fix Prompt Optimization Job validators (GAP-SEC-01)
2. Add Webhook before-request handlers (or verify our router handles these)
3. Add `GATEWAY_SUPPORTED_PROVIDERS` and `GATEWAY_SUPPORTED_MODELS` validators
4. Add internal gateway auth token support (GAP-SEC-03) for MLflow job subprocesses

---

## Notes

**NOTE-01:** Our gateway creation validators (`validate_can_create_gateway`) may be more flexible than upstream's `sender_is_admin`. Upstream requires admin for creating gateway endpoints/secrets/model definitions. Our validator may allow non-admin users with appropriate permissions. This is an intentional design choice, not a gap.

**NOTE-02:** The `ListLoggedModelArtifacts` handler exists in upstream's LOGGED_MODEL_BEFORE_REQUEST_HANDLERS but is NOT in our handlers. This needs investigation — check if this proto exists in MLflow 3.10.

**NOTE-03:** Upstream's `_find_validator()` also handles `GATEWAY_SUPPORTED_PROVIDERS`, `GATEWAY_SUPPORTED_MODELS`, `GATEWAY_PROVIDER_CONFIG`, `GATEWAY_SECRETS_CONFIG` via a separate Flask route mapping. These are discovery/config endpoints for the Gateway UI.
