import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum } from 'src/app/core/configs/permissions';

export interface PermissionsDialogData {
  entityType: EntityEnum;
  entityName: string;
  forEntity: string;
  permission: PermissionEnum;
}
