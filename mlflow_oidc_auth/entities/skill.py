from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._base import PermissionBase


@dataclass
class SkillPermission(PermissionBase):
    """A user or group grant on one skill of MLflow's skill registry.

    MLflow keeps skills unique per ``(workspace, organization, name)``. ``name`` is the grant key:
    the bare skill name, or ``@<organization>/<name>`` for a skill in an organization (see
    ``utils/skill_key.py``). ``workspace`` is the workspace of the skill the grant names.
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
    def from_json(cls, d: Dict[str, Any]) -> "SkillPermission":
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
