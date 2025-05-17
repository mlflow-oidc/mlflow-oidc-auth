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

export interface ExperimentRegexPermissionModel {
  group_id: string;
  permission: PermissionEnum;
  priority: number;
  regex: string;
}

export interface ModelRegexPermissionModel {
  group_id: string;
  permission: PermissionEnum;
  priority: number;
  prompt: boolean;
  regex: string;
}

export interface PromptRegexPermissionModel {
  group_id: string;
  permission: PermissionEnum;
  priority: number;
  prompt: boolean;
  regex: string;
}
