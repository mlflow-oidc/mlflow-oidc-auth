"""Response models for the auth, health and UI routers (#458).

These routers return ``Response`` objects; the models document the bodies they already build and
list exactly those fields.
"""

from typing import Dict, List, Optional

from pydantic import Field

from mlflow_oidc_auth.models._base import ResponseModel


class AuthProvider(ResponseModel):
    """A provider a browser may log in with. Carries nothing about how it is configured."""

    id: str
    display_name: str
    type: str
    login_url: str = Field(..., description="Same-origin path that begins the login")


class AuthProvidersResponse(ResponseModel):
    """``GET /providers``."""

    providers: List[AuthProvider]


class AuthStatusResponse(ResponseModel):
    """``GET /auth/status``."""

    authenticated: bool
    username: Optional[str] = None
    provider: Optional[str] = Field(None, description="Display name of the provider the session came from")


class HealthStatusResponse(ResponseModel):
    """``GET /health`` and ``GET /health/live``."""

    status: str


class ReadinessResponse(ResponseModel):
    """``GET /health/ready`` (200 when ready, 503 otherwise)."""

    status: str = Field(..., description="'ready' or 'not_ready'")
    checks: Dict[str, bool]


class StartupResponse(ResponseModel):
    """``GET /health/startup`` (200 once started, 503 while initializing)."""

    __absent_fields__ = frozenset({"message"})

    status: str = Field(..., description="'started' or 'initializing'")
    oidc_initialized: bool
    providers: Dict[str, bool] = Field(..., description="Per-provider registration outcome")
    message: Optional[str] = Field(None, description="Present only while initializing")


class UiRuntimeConfig(ResponseModel):
    """``GET /oidc/ui/config.json``: the SPA's runtime configuration."""

    basePath: str
    uiPath: str
    provider: str
    authenticated: bool
    gen_ai_gateway_enabled: bool
    workspaces_enabled: bool
