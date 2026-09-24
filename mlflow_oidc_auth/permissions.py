from typing import Iterable
from dataclasses import dataclass

from mlflow import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE


@dataclass
class Permission:
    name: str
    priority: int
    can_read: bool
    can_use: bool
    can_update: bool
    can_delete: bool
    can_manage: bool


READ = Permission(
    name="READ",
    priority=1,
    can_read=True,
    can_use=False,
    can_update=False,
    can_delete=False,
    can_manage=False,
)

USE = Permission(
    name="USE",
    priority=2,
    can_read=True,
    can_use=True,
    can_update=False,
    can_delete=False,
    can_manage=False,
)

EDIT = Permission(
    name="EDIT",
    priority=3,
    can_read=True,
    can_use=True,
    can_update=True,
    can_delete=False,
    can_manage=False,
)

MANAGE = Permission(
    name="MANAGE",
    priority=4,
    can_read=True,
    can_use=True,
    can_update=True,
    can_delete=True,
    can_manage=True,
)

NO_PERMISSIONS = Permission(
    name="NO_PERMISSIONS",
    priority=100,
    can_read=False,
    can_use=False,
    can_update=False,
    can_delete=False,
    can_manage=False,
)

ALL_PERMISSIONS = {
    READ.name: READ,
    USE.name: USE,
    EDIT.name: EDIT,
    MANAGE.name: MANAGE,
    NO_PERMISSIONS.name: NO_PERMISSIONS,
}


def get_permission(permission: str) -> Permission:
    return ALL_PERMISSIONS[permission]


def _validate_permission(permission: str) -> None:
    if permission not in ALL_PERMISSIONS:
        raise MlflowException(
            f"Invalid permission '{permission}'. Valid permissions are: {tuple(ALL_PERMISSIONS)}",
            INVALID_PARAMETER_VALUE,
        )


def compare_permissions(permission1: str, permission2: str) -> bool:
    """
    Compare the priority of two permissions.

    Args:
        permission1 (str): The name of the first permission.
        permission2 (str): The name of the second permission.

    Returns:
        bool: True if the priority of permission1 is less than or equal to the priority of permission2, False otherwise.
    """
    _validate_permission(permission1)
    _validate_permission(permission2)
    return ALL_PERMISSIONS[permission1].priority <= ALL_PERMISSIONS[permission2].priority


_CAPABILITIES = ("can_read", "can_use", "can_update", "can_delete", "can_manage")


def intersect_permissions(permissions: Iterable[Permission]) -> Permission:
    """The capabilities held on EVERY one of ``permissions``, as a real permission level.

    Used when a request names more than one resource for a single field — the same id
    spelled in two request sources with different values (issues #285, #288). The
    caller may do only what it may do on all of them. An empty input yields
    ``NO_PERMISSIONS``: resolving nothing must never mean allow.

    The result is always one of ``ALL_PERMISSIONS``, so its ``name`` is a valid key for
    ``get_permission`` / ``compare_permissions`` and its ``priority`` is that level's
    own. It is the most capable level whose flags are all contained in the logical AND
    of the inputs' flags. The built-in levels are totally ordered by their flags, so for
    them this is exactly the weakest input; anything else rounds DOWN, never up.

    ``priority`` is deliberately not used to pick the weakest: it is a resolution
    order, not a capability order (``NO_PERMISSIONS`` has the highest priority and no
    capabilities), so neither ``min`` nor ``max`` of it yields the weakest member.

    Parameters:
        permissions: The permissions resolved for each referenced resource.

    Returns:
        The single input when there is one, otherwise the ``ALL_PERMISSIONS`` level
        described above.
    """
    resolved = list(permissions)
    if not resolved:
        return NO_PERMISSIONS
    if len(resolved) == 1:
        return resolved[0]
    held = {flag: all(getattr(p, flag) for p in resolved) for flag in _CAPABILITIES}
    contained = [level for level in ALL_PERMISSIONS.values() if all(held[flag] or not getattr(level, flag) for flag in _CAPABILITIES)]
    # NO_PERMISSIONS has no flags, so it is always contained and the list is never empty.
    return max(contained, key=lambda level: sum(getattr(level, flag) for flag in _CAPABILITIES))
