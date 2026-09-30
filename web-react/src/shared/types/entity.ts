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

export type GroupDetails = {
  group_name: string;
  external_id: string | null;
  member_count: number;
};

export type PermissionLevel =
  | "READ"
  | "USE"
  | "EDIT"
  | "MANAGE"
  | "NO_PERMISSIONS";

export type PermissionKind = "user" | "group" | "regex" | "group-regex" | "fallback" | "workspace" | "workspace-deny" | "service-account";

export type PermissionType =
  | "experiments"
  | "models"
  | "prompts"
  | "ai-endpoints"
  | "ai-secrets"
  | "ai-models";

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
export type BasePatternPermission = {
  id: number;
  permission: PermissionLevel;
  priority: number;
  regex: string;
  user_id?: number;
  group_id?: number;
};

export type ExperimentPatternPermission = BasePatternPermission;

export type ModelPatternPermission = BasePatternPermission & {
  prompt: boolean;
};

export type PromptPatternPermission = ModelPatternPermission;

export type PatternPermissionItem =
  | ExperimentPatternPermission
  | ModelPatternPermission;

export type DeletedExperiment = {
  experiment_id: string;
  name: string;
  lifecycle_stage: string;
  artifact_location: string;
  tags: Record<string, string>;
  creation_time: number;
  last_update_time: number;
};

export type DeletedRun = {
  run_id: string;
  experiment_id: string;
  run_name: string;
  status: string;
  start_time: number;
  end_time: number | null;
  lifecycle_stage: string;
};

export type CleanupFailure = {
  run_id?: string;
  experiment_id?: string;
  error: string;
};

export type CleanupTrashResponse = {
  deleted_runs: string[];
  deleted_experiments: string[];
  total_deleted_runs: number;
  total_deleted_experiments: number;
  failed_runs?: CleanupFailure[];
  failed_experiments?: CleanupFailure[];
};

export type WebhookStatus = "ACTIVE" | "DISABLED";

export type Webhook = {
  webhook_id: string;
  name: string;
  url: string;
  events: string[];
  status: WebhookStatus;
  description?: string;
  secret?: string;
  creation_timestamp: number;
  last_updated_timestamp: number;
};

export type WebhookCreateRequest = {
  name: string;
  url: string;
  events: string[];
  status?: WebhookStatus;
  secret?: string;
  description?: string;
};

export type WebhookUpdateRequest = Partial<WebhookCreateRequest>;

export type WebhookTestRequest = {
  event?: string;
  payload?: Record<string, unknown>;
};

export type WebhookTestResponse = {
  success: boolean;
  response_status?: number;
  response_body?: string;
  error_message?: string;
};

// Gateway types
export type GatewayEndpointListItem = {
  name: string;
  type: string;
  description: string;
  route_type: string;
  auth_type: string;
};

export type GatewaySecretListItem = {
  key: string;
};

export type GatewayModelListItem = {
  name: string;
  source: string;
};

// Workspace types
export type WorkspaceListItem = {
  name: string;
  description: string;
  default_artifact_root: string;
};

export type WorkspaceListResponse = {
  workspaces: WorkspaceListItem[];
};

export type WorkspaceUserPermission = {
  workspace: string;
  username: string;
  permission: PermissionLevel;
};

export type WorkspaceGroupPermission = {
  workspace: string;
  group_name: string;
  permission: PermissionLevel;
};

/** How a workspace group rule behaves: `report` writes nothing, `enforce` grants. */
export type WorkspaceRuleMode = "report" | "enforce";

/** A permission a workspace group rule may grant. `NO_PERMISSIONS` is never one. */
export type WorkspaceRulePermission = "READ" | "USE" | "EDIT" | "MANAGE";

/** An admin-managed rule attaching groups to workspaces by group name (issue #418). */
export type WorkspaceRule = {
  id: number;
  name: string;
  pattern: string;
  permission: WorkspaceRulePermission;
  mode: WorkspaceRuleMode;
  enabled: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkspaceRuleList = {
  rules: WorkspaceRule[];
  /** WORKSPACE_RULES_MAX_PERMISSION: no rule may grant more. */
  max_permission: WorkspaceRulePermission;
  /** The permissions a rule may grant under the ceiling, lowest first. */
  allowed_permissions: WorkspaceRulePermission[];
};

export type WorkspaceRuleChangeAction =
  | "grant"
  | "update"
  | "keep"
  | "remove"
  | "skip"
  | "shadowed";

/** One line of a rule's plan: what happens to one group's grant on one workspace. */
export type WorkspaceRuleChange = {
  action: WorkspaceRuleChangeAction;
  group: string;
  workspace: string;
  permission: string | null;
  reason: string | null;
  previous: string | null;
  /** Whether it was written. Always false in a preview and for a report-mode rule. */
  applied: boolean;
};

export type WorkspaceRulePlan = {
  rule: WorkspaceRule | null;
  changes: WorkspaceRuleChange[];
};

export type WorkspaceRuleCreateRequest = {
  name: string;
  pattern: string;
  permission: WorkspaceRulePermission;
  mode: WorkspaceRuleMode;
  enabled: boolean;
};

export type WorkspaceRuleUpdateRequest = Partial<WorkspaceRuleCreateRequest>;

export type WorkspaceCrudCreateRequest = {
  name: string;
  description?: string;
  default_artifact_root?: string;
};

export type WorkspaceCrudUpdateRequest = {
  description: string;
  default_artifact_root?: string;
};

export type WorkspaceCrudResponse = {
  name: string;
  description: string;
  default_artifact_root: string | null;
};

export type WorkspaceMemberCounts = {
  users: number;
  groups: number;
};
