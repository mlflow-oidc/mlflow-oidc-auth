"""SCIM 2.0 wire models (RFC 7643 / RFC 7644), hand-written and limited to what ``/scim/v2`` serves.

Only the ``User`` resource is implemented (#322); ``Group`` is #323. The shapes here are the
subset of the core schema this plugin can actually persist — anything else a client sends in a
``POST`` or ``PUT`` body is accepted and ignored, while a ``PATCH`` naming an attribute outside
this subset is refused with ``invalidPath`` so a directory never believes a write landed when
it did not.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

SCIM_CONTENT_TYPE = "application/scim+json"

USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
LIST_RESPONSE_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
PATCH_OP_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
SERVICE_PROVIDER_CONFIG_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"
RESOURCE_TYPE_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:ResourceType"
SCHEMA_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Schema"


class ScimName(BaseModel):
    """The ``name`` complex attribute. Only ``formatted`` is persisted, as the display name."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    formatted: Optional[str] = None
    given_name: Optional[str] = Field(default=None, alias="givenName")
    family_name: Optional[str] = Field(default=None, alias="familyName")

    def display(self) -> Optional[str]:
        if self.formatted:
            return self.formatted
        parts = [p for p in (self.given_name, self.family_name) if p]
        return " ".join(parts) or None


class ScimUserInput(BaseModel):
    """A ``POST`` or ``PUT`` body. Unknown attributes are ignored, as RFC 7644 permits."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    schemas: List[str] = Field(default_factory=lambda: [USER_SCHEMA])
    user_name: str = Field(alias="userName", min_length=1)
    external_id: Optional[str] = Field(default=None, alias="externalId")
    display_name: Optional[str] = Field(default=None, alias="displayName")
    name: Optional[ScimName] = None
    # None means "not sent": POST treats it as true, PUT keeps the current state, so a PUT that
    # leaves the attribute out never reactivates a deprovisioned user.
    active: Any = None

    def resolved_display_name(self) -> str:
        return self.display_name or (self.name.display() if self.name else None) or self.user_name


class ScimPatchOperation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    op: str
    path: Optional[str] = None
    value: Any = None


class ScimPatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    schemas: List[str] = Field(default_factory=lambda: [PATCH_OP_SCHEMA])
    operations: List[ScimPatchOperation] = Field(alias="Operations", min_length=1)


class ScimMeta(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    resource_type: str = Field(default="User", alias="resourceType")
    created: Optional[str] = None
    last_modified: Optional[str] = Field(default=None, alias="lastModified")
    location: Optional[str] = None


class ScimUser(BaseModel):
    """A ``User`` as served. ``id`` is the username — see ``docs/scim.md`` for why."""

    model_config = ConfigDict(populate_by_name=True)

    schemas: List[str] = Field(default_factory=lambda: [USER_SCHEMA])
    id: str
    user_name: str = Field(alias="userName")
    external_id: Optional[str] = Field(default=None, alias="externalId")
    display_name: Optional[str] = Field(default=None, alias="displayName")
    name: Optional[Dict[str, str]] = None
    active: bool
    meta: ScimMeta

    def to_wire(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class ScimListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schemas: List[str] = Field(default_factory=lambda: [LIST_RESPONSE_SCHEMA])
    total_results: int = Field(alias="totalResults")
    start_index: int = Field(alias="startIndex")
    items_per_page: int = Field(alias="itemsPerPage")
    resources: List[Dict[str, Any]] = Field(default_factory=list, alias="Resources")

    def to_wire(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True)


class ScimError(BaseModel):
    """RFC 7644 §3.12 error body. ``status`` is a string on the wire, per the RFC."""

    model_config = ConfigDict(populate_by_name=True)

    schemas: List[str] = Field(default_factory=lambda: [ERROR_SCHEMA])
    status: str
    scim_type: Optional[str] = Field(default=None, alias="scimType")
    detail: Optional[str] = None

    def to_wire(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class CreateScimTokenRequest(BaseModel):
    """Admin API: issue a SCIM token."""

    name: str = Field(..., min_length=1, max_length=200, description="Unique label, e.g. the directory it is for")
    expires_at: Optional[str] = Field(default=None, description="ISO 8601 expiry; omit for a token that does not expire")


class UserActiveRequest(BaseModel):
    """Admin API: activate or deactivate a user."""

    active: bool
    admin_override: bool = Field(default=False, description="Break glass: write a row another source owns. Always audited.")
