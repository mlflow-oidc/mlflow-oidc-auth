export const STATIC_API_ENDPOINTS = {
  ALL_GROUPS: "/api/2.0/mlflow/permissions/groups",
  ALL_EXPERIMENTS: "/api/2.0/mlflow/permissions/experiments",
  ALL_MODELS: "/api/2.0/mlflow/permissions/registered-models",
  ALL_PROMPTS: "/api/2.0/mlflow/permissions/prompts",

  // User management
  CREATE_ACCESS_TOKEN: "/api/2.0/mlflow/users/access-token",
  GET_CURRENT_USER: "/api/2.0/mlflow/users/current",
  USERS_RESOURCE: "/api/2.0/mlflow/users",

  // Trash management
  TRASH_EXPERIMENTS: "/oidc/trash/experiments",
  TRASH_RUNS: "/oidc/trash/runs",
  TRASH_CLEANUP: "/oidc/trash/cleanup",

  // Webhook management
  WEBHOOKS_RESOURCE: "/oidc/webhook",
} as const;

export const DYNAMIC_API_ENDPOINTS = {
  // User permissions for resources
  GET_USER_DETAILS: (userName: string) => `/api/2.0/mlflow/users/${userName}`,
  USER_EXPERIMENT_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/experiments`,
  USER_EXPERIMENT_PERMISSION: (userName: string, experimentId: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/experiments/${experimentId}`,
  USER_MODEL_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/registered-models`,
  USER_MODEL_PERMISSION: (userName: string, modelName: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/registered-models/${modelName}`,
  USER_PROMPT_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/prompts`,
  USER_PROMPT_PERMISSION: (userName: string, promptName: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/prompts/${promptName}`,

  // User pattern permissions
  USER_EXPERIMENT_PATTERN_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/experiment-patterns`,
  USER_EXPERIMENT_PATTERN_PERMISSION: (userName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/experiment-patterns/${patternId}`,
  USER_MODEL_PATTERN_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/registered-models-patterns`,
  USER_MODEL_PATTERN_PERMISSION: (userName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/registered-models-patterns/${patternId}`,
  USER_PROMPT_PATTERN_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/prompts-patterns`,
  USER_PROMPT_PATTERN_PERMISSION: (userName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/users/${userName}/prompts-patterns/${patternId}`,

  // Resource user permissions
  EXPERIMENT_USER_PERMISSIONS: (experimentId: string) =>
    `/api/2.0/mlflow/permissions/experiments/${encodeURIComponent(String(experimentId))}/users`,
  MODEL_USER_PERMISSIONS: (modelName: string) =>
    `/api/2.0/mlflow/permissions/registered-models/${encodeURIComponent(String(modelName))}/users`,
  PROMPT_USER_PERMISSIONS: (promptName: string) =>
    `/api/2.0/mlflow/permissions/prompts/${encodeURIComponent(String(promptName))}/users`,

  // Group permissions for resources
  GROUP_EXPERIMENT_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/experiments`,
  GROUP_EXPERIMENT_PERMISSION: (groupName: string, experimentId: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/experiments/${experimentId}`,
  GROUP_MODEL_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/registered-models`,
  GROUP_MODEL_PERMISSION: (groupName: string, modelName: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/registered-models/${modelName}`,
  GROUP_PROMPT_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/prompts`,
  GROUP_PROMPT_PERMISSION: (groupName: string, promptName: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/prompts/${promptName}`,

  // Group pattern permissions
  GROUP_EXPERIMENT_PATTERN_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/experiment-patterns`,
  GROUP_EXPERIMENT_PATTERN_PERMISSION: (groupName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/experiment-patterns/${patternId}`,
  GROUP_MODEL_PATTERN_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/registered-models-patterns`,
  GROUP_MODEL_PATTERN_PERMISSION: (groupName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/registered-models-patterns/${patternId}`,
  GROUP_PROMPT_PATTERN_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/prompts-patterns`,
  GROUP_PROMPT_PATTERN_PERMISSION: (groupName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/groups/${groupName}/prompts-patterns/${patternId}`,

  // Resource group permissions
  EXPERIMENT_GROUP_PERMISSIONS: (experimentId: string) =>
    `/api/2.0/mlflow/permissions/experiments/${encodeURIComponent(String(experimentId))}/groups`,
  MODEL_GROUP_PERMISSIONS: (modelName: string) =>
    `/api/2.0/mlflow/permissions/registered-models/${encodeURIComponent(String(modelName))}/groups`,
  PROMPT_GROUP_PERMISSIONS: (promptName: string) =>
    `/api/2.0/mlflow/permissions/prompts/${encodeURIComponent(String(promptName))}/groups`,

  // Trash management
  RESTORE_EXPERIMENT: (experimentId: string) => `/oidc/trash/experiments/${experimentId}/restore`,
  RESTORE_RUN: (runId: string) => `/oidc/trash/runs/${runId}/restore`,

  // Webhook management
  WEBHOOK_DETAILS: (webhookId: string) => `/oidc/webhook/${webhookId}`,
  TEST_WEBHOOK: (webhookId: string) => `/oidc/webhook/${webhookId}/test`,
} as const;

export type StaticEndpointKey = keyof typeof STATIC_API_ENDPOINTS;
export type DynamicEndpointKey = keyof typeof DYNAMIC_API_ENDPOINTS;

type DynamicEndpointFunction<K extends DynamicEndpointKey> = (typeof DYNAMIC_API_ENDPOINTS)[K];

export type PathParams<K extends DynamicEndpointKey> = Parameters<DynamicEndpointFunction<K>>;
