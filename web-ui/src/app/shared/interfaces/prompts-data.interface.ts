import { PermissionEnum, PermissionTypeEnum } from 'src/app/core/configs/permissions';

export interface PromptModel {
  aliases: Record<string, unknown>;
  description: string;
  name: string;
  tags: Record<string, unknown>;
}

export interface PromptPermissionModel {
  name: string;
  permission: PermissionEnum;
  type: PermissionTypeEnum;
}

export interface PromptUserListModel {
  permission: PermissionEnum;
  username: string;
}
