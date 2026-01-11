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

export type PermissionLevel = "READ" | "EDIT" | "MANAGE" | "NO_PERMISSIONS";

export type PermissionKind = "user" | "group" | "fallback" | "service-account";

export type PermissionType = "experiments" | "models" | "prompts";

export type EntityPermission = {
  kind: PermissionKind;
  permission: PermissionLevel;
  name: string;
};

export type ExperimentPermission = {
  name: string;
  id: string;
  permission: PermissionLevel;
  kind: PermissionKind;
};

export type ModelPermission = {
  name: string;
  permission: PermissionLevel;
  kind: PermissionKind;
};

export type PromptPermission = ModelPermission;

export type PermissionItem = ExperimentPermission | ModelPermission;

export type AnyPermissionItem = PermissionItem | PatternPermissionItem;

// Pattern permission types for Regex Mode
export type ExperimentPatternPermission = {
  id: number;
  permission: PermissionLevel;
  priority: number;
  regex: string;
  user_id?: number;
  group_id?: number;
};

export type ModelPatternPermission = {
  id: number;
  permission: PermissionLevel;
  priority: number;
  prompt: boolean;
  regex: string;
  user_id?: number;
  group_id?: number;
};

export type PromptPatternPermission = ModelPatternPermission;

export type PatternPermissionItem = ExperimentPatternPermission | ModelPatternPermission;