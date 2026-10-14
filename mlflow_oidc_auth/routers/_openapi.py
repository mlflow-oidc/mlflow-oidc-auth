"""OpenAPI declarations for routes whose response is not a JSON model (#458).

Every route under ``routers/`` declares its response: a Pydantic ``response_model``, or an
explicit ``response_class`` plus ``responses=`` for a redirect, a file, an XML document or a SCIM
body. The handlers keep returning their own ``Response`` objects, so nothing here changes what a
client receives; it only changes what the OpenAPI document says about it.
"""

from fastapi.responses import JSONResponse, Response

from mlflow_oidc_auth.models.scim import SCIM_CONTENT_TYPE


class ScimJSONResponse(JSONResponse):
    """A SCIM 2.0 body (RFC 7644), served as ``application/scim+json``."""

    media_type = SCIM_CONTENT_TYPE


class SamlMetadataResponse(Response):
    """A SAML 2.0 metadata document."""

    media_type = "application/samlmetadata+xml"


#: A browser redirect. The body is empty; the target is in ``Location``.
REDIRECT_RESPONSES = {
    302: {"description": "Redirect; the target is in the Location header"},
}
