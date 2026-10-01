from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._base import PermissionBase


@dataclass
class MCPServerPermission(PermissionBase):
    """A user or group grant on one MCP server of MLflow's MCP server registry.

    MLflow keeps MCP servers unique per ``(workspace, name)``; ``name`` is the registry name
    (``<reverse-dns namespace>/<slug>``, e.g. ``com.example/weather``) and ``workspace`` the
    workspace of the server the grant names.
    """

    def __init__(self, name: str, permission: str, user_id: Optional[int] = None, group_id: Optional[int] = None, workspace: Optional[str] = None):
        super().__init__(instance=name, permission=permission, user_id=user_id, group_id=group_id)
        self.workspace = workspace

    @property
    def name(self) -> str:
        return self.instance

    def to_json(self) -> Dict[str, Any]:
        d = super().to_json()
        d["name"] = d.pop("instance")
        d["workspace"] = self.workspace
        return d

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "MCPServerPermission":
        user_id = d.get("user_id")
        group_id = d.get("group_id")
        if user_id is not None:
            try:
                user_id = int(user_id)
            except (TypeError, ValueError):
                raise ValueError("user_id must be an integer")
        if group_id is not None:
            try:
                group_id = int(group_id)
            except (TypeError, ValueError):
                raise ValueError("group_id must be an integer")
        return cls(name=d["name"], permission=d["permission"], user_id=user_id, group_id=group_id, workspace=d.get("workspace"))
