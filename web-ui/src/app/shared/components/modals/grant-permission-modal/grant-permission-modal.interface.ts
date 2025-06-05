import { EntityEnum } from 'src/app/core/configs/core';
import { PermissionEnum } from 'src/app/core/configs/permissions';

export type WithNameAndId = {
  id: string;
  name: string;
  [key: string]: any;
};

export interface GrantPermissionModalData {
  targetName: string;
  entityType: EntityEnum;
  entities: WithNameAndId[];
}

export interface GrantPermissionModalResult {
  permission: PermissionEnum;
  entity: WithNameAndId;
}
