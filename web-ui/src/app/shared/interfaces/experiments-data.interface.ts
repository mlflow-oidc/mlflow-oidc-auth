import { PermissionEnum, PermissionTypeEnum } from 'src/app/core/configs/permissions';

export interface ExperimentModel {
  id: string;
  name: string;
  tags: Record<string, unknown>;
}

export interface ExperimentsForUserModel {
  experiments: ExperimentForUserModel[];
}

export interface ExperimentForUserModel {
  id: string;
  name: string;
  permission: PermissionEnum;
  type: PermissionTypeEnum;
}

export interface UserPermissionModel {
  permission: PermissionEnum;
  username: string;
}
