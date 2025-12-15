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

export type PermissionLevel = "READ" | "WRITE" | "MANAGE";

export type PermissionKind = "user" | "group";

export type EntityPermission = {
  kind: PermissionKind;
  permission: PermissionLevel;
  username: string;
};
