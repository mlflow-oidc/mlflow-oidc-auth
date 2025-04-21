import { PermissionEnum } from 'src/app/core/configs/permissions';

export interface GroupsDataModel {
  groups: string[];
}

export interface ExperimentModel {
  id: string;
  name: string;
  permission: PermissionEnum;
}

export interface ModelModel {
  name: string;
  permission: PermissionEnum;
}
