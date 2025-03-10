from dataclasses import dataclass

from mlflow import MlflowException
from mlflow.protos.databricks_pb2 import INVALID_PARAMETER_VALUE


@dataclass
class Permission:
    name: str
    priority: int
    can_read: bool
    can_update: bool
    can_delete: bool
    can_manage: bool


READ = Permission(
    name="READ",
    priority=1,
    can_read=True,
    can_update=False,
    can_delete=False,
    can_manage=False,
)

EDIT = Permission(
    name="EDIT",
    priority=2,
    can_read=True,
    can_update=True,
    can_delete=False,
    can_manage=False,
)

MANAGE = Permission(
    name="MANAGE",
    priority=3,
    can_read=True,
    can_update=True,
    can_delete=True,
    can_manage=True,
)

NO_PERMISSIONS = Permission(
    name="NO_PERMISSIONS",
    priority=0,
    can_read=False,
    can_update=False,
    can_delete=False,
    can_manage=False,
)

ALL_PERMISSIONS = {
    READ.name: READ,
    EDIT.name: EDIT,
    MANAGE.name: MANAGE,
    NO_PERMISSIONS.name: NO_PERMISSIONS,
}


def get_permission(permission: str) -> Permission:
    return ALL_PERMISSIONS[permission]


def _validate_permission(permission: str):
    if permission not in ALL_PERMISSIONS:
        raise MlflowException(
            f"Invalid permission '{permission}'. Valid permissions are: {tuple(ALL_PERMISSIONS)}",
            INVALID_PARAMETER_VALUE,
        )


def compare_permissions(permission1: str, permission2: str, strict: bool=False) -> bool:
    """Compare two permissions permission1 and permission2

    If permission1 has a lower priorty than permission2, the return value will be True. In case the argument
    strict has the non-default value of True, the priority of permission1 must be strictly lower than the
    priority of permission2

    Args:
        permission1: The string representation of the first permission
        permission2: The string representation of the second permission
        strict: Boolean indicating whether the comparison should be exected in strictly lower or not

    Returns:
        True if permission1 is having (strictly) lower priority than permission2
    """
    _validate_permission(permission1)
    _validate_permission(permission2)

    if strict:
        return ALL_PERMISSIONS[permission1].priority < ALL_PERMISSIONS[permission2].priority
    else:
        return ALL_PERMISSIONS[permission1].priority <= ALL_PERMISSIONS[permission2].priority
