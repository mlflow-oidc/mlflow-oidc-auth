"""The base class of the plugin's response models (#458)."""

from __future__ import annotations

from typing import Any, ClassVar, Dict, FrozenSet

from pydantic import BaseModel, ConfigDict


def _drop_absent_fields(schema: Dict[str, Any], model: type) -> None:
    """Keep the fields a body may omit out of the schema's ``required`` list."""
    absent = getattr(model, "__absent_fields__", frozenset())
    if absent and "required" in schema:
        schema["required"] = [name for name in schema["required"] if name not in absent]
        if not schema["required"]:
            del schema["required"]


class ResponseModel(BaseModel):
    """A response body as the server sends it.

    Every field is in every response — a field with a default is still sent, as its default — so
    the serialization schema lists every field as required, and the generated UI types do not
    make the client handle a missing value the server never omits. A field that a body really
    can leave out (``failed_runs`` when nothing failed) is named in ``__absent_fields__`` and
    stays optional.

    Response models list exactly the fields the handler returns. Never ``extra="allow"``.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True, json_schema_extra=_drop_absent_fields)

    #: Fields a body may omit entirely; they stay out of the schema's ``required`` list.
    __absent_fields__: ClassVar[FrozenSet[str]] = frozenset()
