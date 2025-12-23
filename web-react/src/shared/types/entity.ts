export type ExperimentListItem = {
  id: string;
  name: string;
  tags: Record<string, string>;
};

export type ModelListItem = {
  aliases: string;
  description: string;
  name: string;
  tags: Record<string, string>;
};

export type PromptListItem = ModelListItem;

export type PermissionLevel = "READ" | "WRITE" | "MANAGE" | "NO_PERMISSIONS";

export type PermissionKind = "user" | "group";

export type PermissionType = "experiments" | "models" | "prompts";

export type EntityPermission = {
  kind: PermissionKind;
  permission: PermissionLevel;
  username: string;
};

export type ExperimentPermission = {
  name: string;
  id: string;
  permission: PermissionLevel;
  type: PermissionKind;
};

export type ModelPermission = {
  name: string;
  permission: PermissionLevel;
  type: PermissionKind;
};

export type PromptPermission = ModelPermission;
