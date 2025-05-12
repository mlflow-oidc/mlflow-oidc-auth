import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum } from 'src/app/core/configs/permissions';

export interface ManageRegexModalData {
  regex: string;
  priority: number;
  permission: PermissionEnum;
}
