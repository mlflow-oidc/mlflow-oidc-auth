export const STATIC_API_ENDPOINTS = {
  ALL_GROUPS: "/api/2.0/mlflow/permissions/groups",
  ALL_EXPERIMENTS: "/api/2.0/mlflow/permissions/experiments",
  ALL_MODELS: "/api/2.0/mlflow/permissions/registered-models",
  ALL_PROMPTS: "/api/2.0/mlflow/permissions/prompts",

  // Gateway management
  ALL_GATEWAY_ENDPOINTS: "/api/2.0/mlflow/permissions/gateways/endpoints",
  ALL_GATEWAY_SECRETS: "/api/2.0/mlflow/permissions/gateways/secrets",
  ALL_GATEWAY_MODELS: "/api/2.0/mlflow/permissions/gateways/model-definitions",

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
  GET_USER_DETAILS: (userName: string) =>
    `/api/2.0/mlflow/users/${encodeURIComponent(userName)}`,
  USER_EXPERIMENT_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/experiments`,
  USER_EXPERIMENT_PERMISSION: (userName: string, experimentId: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/experiments/${encodeURIComponent(experimentId)}`,
  USER_MODEL_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/registered-models`,
  USER_MODEL_PERMISSION: (userName: string, modelName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/registered-models/${encodeURIComponent(modelName)}`,
  USER_PROMPT_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/prompts`,
  USER_PROMPT_PERMISSION: (userName: string, promptName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/prompts/${encodeURIComponent(promptName)}`,

  // User pattern permissions
  USER_EXPERIMENT_PATTERN_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/experiment-patterns`,
  USER_EXPERIMENT_PATTERN_PERMISSION: (userName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/experiment-patterns/${encodeURIComponent(patternId)}`,
  USER_MODEL_PATTERN_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/registered-models-patterns`,
  USER_MODEL_PATTERN_PERMISSION: (userName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/registered-models-patterns/${encodeURIComponent(patternId)}`,
  USER_PROMPT_PATTERN_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/prompts-patterns`,
  USER_PROMPT_PATTERN_PERMISSION: (userName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/prompts-patterns/${encodeURIComponent(patternId)}`,

  // Resource user permissions
  EXPERIMENT_USER_PERMISSIONS: (experimentId: string) =>
    `/api/2.0/mlflow/permissions/experiments/${encodeURIComponent(String(experimentId))}/users`,
  MODEL_USER_PERMISSIONS: (modelName: string) =>
    `/api/2.0/mlflow/permissions/registered-models/${encodeURIComponent(String(modelName))}/users`,
  PROMPT_USER_PERMISSIONS: (promptName: string) =>
    `/api/2.0/mlflow/permissions/prompts/${encodeURIComponent(String(promptName))}/users`,

  // Group permissions for resources
  GROUP_EXPERIMENT_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/experiments`,
  GROUP_EXPERIMENT_PERMISSION: (groupName: string, experimentId: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/experiments/${encodeURIComponent(experimentId)}`,
  GROUP_MODEL_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/registered-models`,
  GROUP_MODEL_PERMISSION: (groupName: string, modelName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/registered-models/${encodeURIComponent(modelName)}`,
  GROUP_PROMPT_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/prompts`,
  GROUP_PROMPT_PERMISSION: (groupName: string, promptName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/prompts/${encodeURIComponent(promptName)}`,

  // Group pattern permissions
  GROUP_EXPERIMENT_PATTERN_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/experiment-patterns`,
  GROUP_EXPERIMENT_PATTERN_PERMISSION: (groupName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/experiment-patterns/${encodeURIComponent(patternId)}`,
  GROUP_MODEL_PATTERN_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/registered-models-patterns`,
  GROUP_MODEL_PATTERN_PERMISSION: (groupName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/registered-models-patterns/${encodeURIComponent(patternId)}`,
  GROUP_PROMPT_PATTERN_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/prompts-patterns`,
  GROUP_PROMPT_PATTERN_PERMISSION: (groupName: string, patternId: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/prompts-patterns/${encodeURIComponent(patternId)}`,

  // Resource group permissions
  EXPERIMENT_GROUP_PERMISSIONS: (experimentId: string) =>
    `/api/2.0/mlflow/permissions/experiments/${encodeURIComponent(String(experimentId))}/groups`,
  MODEL_GROUP_PERMISSIONS: (modelName: string) =>
    `/api/2.0/mlflow/permissions/registered-models/${encodeURIComponent(String(modelName))}/groups`,
  PROMPT_GROUP_PERMISSIONS: (promptName: string) =>
    `/api/2.0/mlflow/permissions/prompts/${encodeURIComponent(String(promptName))}/groups`,

  // Gateway Resource user permissions
  GATEWAY_ENDPOINT_USER_PERMISSIONS: (name: string) =>
    `/api/2.0/mlflow/permissions/gateways/endpoints/${encodeURIComponent(String(name))}/users`,
  GATEWAY_SECRET_USER_PERMISSIONS: (name: string) =>
    `/api/2.0/mlflow/permissions/gateways/secrets/${encodeURIComponent(String(name))}/users`,
  GATEWAY_MODEL_USER_PERMISSIONS: (name: string) =>
    `/api/2.0/mlflow/permissions/gateways/model-definitions/${encodeURIComponent(String(name))}/users`,

  // Gateway Resource group permissions
  GATEWAY_ENDPOINT_GROUP_PERMISSIONS: (name: string) =>
    `/api/2.0/mlflow/permissions/gateways/endpoints/${encodeURIComponent(String(name))}/groups`,
  GATEWAY_SECRET_GROUP_PERMISSIONS: (name: string) =>
    `/api/2.0/mlflow/permissions/gateways/secrets/${encodeURIComponent(String(name))}/groups`,
  GATEWAY_MODEL_GROUP_PERMISSIONS: (name: string) =>
    `/api/2.0/mlflow/permissions/gateways/model-definitions/${encodeURIComponent(String(name))}/groups`,

  // Gateway Group permissions for resources
  GROUP_GATEWAY_ENDPOINT_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/endpoints`,
  GROUP_GATEWAY_ENDPOINT_PERMISSION: (groupName: string, name: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/endpoints/${encodeURIComponent(name)}`,

  GROUP_GATEWAY_SECRET_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/secrets`,
  GROUP_GATEWAY_SECRET_PERMISSION: (groupName: string, name: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/secrets/${encodeURIComponent(name)}`,

  GROUP_GATEWAY_MODEL_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/model-definitions`,
  GROUP_GATEWAY_MODEL_PERMISSION: (groupName: string, name: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/model-definitions/${encodeURIComponent(name)}`,

  // Gateway Group pattern permissions
  GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/endpoints-patterns`,
  GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSION: (
    groupName: string,
    patternId: string,
  ) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/endpoints-patterns/${encodeURIComponent(patternId)}`,

  GROUP_GATEWAY_SECRET_PATTERN_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/secrets-patterns`,
  GROUP_GATEWAY_SECRET_PATTERN_PERMISSION: (
    groupName: string,
    patternId: string,
  ) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/secrets-patterns/${encodeURIComponent(patternId)}`,

  GROUP_GATEWAY_MODEL_PATTERN_PERMISSIONS: (groupName: string) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/model-definitions-patterns`,
  GROUP_GATEWAY_MODEL_PATTERN_PERMISSION: (
    groupName: string,
    patternId: string,
  ) =>
    `/api/2.0/mlflow/permissions/groups/${encodeURIComponent(groupName)}/gateways/model-definitions-patterns/${encodeURIComponent(patternId)}`,

  // Gateway User permissions for resources
  USER_GATEWAY_ENDPOINT_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/endpoints`,
  USER_GATEWAY_ENDPOINT_PERMISSION: (userName: string, name: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/endpoints/${encodeURIComponent(name)}`,

  USER_GATEWAY_SECRET_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/secrets`,
  USER_GATEWAY_SECRET_PERMISSION: (userName: string, name: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/secrets/${encodeURIComponent(name)}`,

  USER_GATEWAY_MODEL_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/model-definitions`,
  USER_GATEWAY_MODEL_PERMISSION: (userName: string, name: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/model-definitions/${encodeURIComponent(name)}`,

  // Gateway User pattern permissions
  USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/endpoints-patterns`,
  USER_GATEWAY_ENDPOINT_PATTERN_PERMISSION: (
    userName: string,
    patternId: string,
  ) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/endpoints-patterns/${encodeURIComponent(patternId)}`,

  USER_GATEWAY_SECRET_PATTERN_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/secrets-patterns`,
  USER_GATEWAY_SECRET_PATTERN_PERMISSION: (
    userName: string,
    patternId: string,
  ) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/secrets-patterns/${encodeURIComponent(patternId)}`,

  USER_GATEWAY_MODEL_PATTERN_PERMISSIONS: (userName: string) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/model-definitions-patterns`,
  USER_GATEWAY_MODEL_PATTERN_PERMISSION: (
    userName: string,
    patternId: string,
  ) =>
    `/api/2.0/mlflow/permissions/users/${encodeURIComponent(userName)}/gateways/model-definitions-patterns/${encodeURIComponent(patternId)}`,

  // Trash management
  RESTORE_EXPERIMENT: (experimentId: string) =>
    `/oidc/trash/experiments/${encodeURIComponent(experimentId)}/restore`,
  RESTORE_RUN: (runId: string) =>
    `/oidc/trash/runs/${encodeURIComponent(runId)}/restore`,

  // Webhook management
  WEBHOOK_DETAILS: (webhookId: string) =>
    `/oidc/webhook/${encodeURIComponent(webhookId)}`,
  TEST_WEBHOOK: (webhookId: string) =>
    `/oidc/webhook/${encodeURIComponent(webhookId)}/test`,
} as const;

export type StaticEndpointKey = keyof typeof STATIC_API_ENDPOINTS;
export type DynamicEndpointKey = keyof typeof DYNAMIC_API_ENDPOINTS;

type DynamicEndpointFunction<K extends DynamicEndpointKey> =
  (typeof DYNAMIC_API_ENDPOINTS)[K];

export type PathParams<K extends DynamicEndpointKey> = Parameters<
  DynamicEndpointFunction<K>
>;
