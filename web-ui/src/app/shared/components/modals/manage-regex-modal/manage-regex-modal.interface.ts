import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum } from 'src/app/core/configs/permissions';

export interface ManageRegexModalData {
  entityType: EntityEnum;
  entities: { id: string; name: string }[];
}

export interface ManageRegexModalResult {
  entity: { id: string; name: string };
  regex: string;
  priority: number;
  permission: PermissionEnum;
}
