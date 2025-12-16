export type DynamicPathParams = {
  experimentId: string;
  // userName: string;
  // modelName: string;
  // promptName: string;
  // groupName: string;
};

export const STATIC_API_ENDPOINTS = {
  ALL_GROUPS: "/api/2.0/mlflow/permissions/groups",
  ALL_EXPERIMENTS: "/api/2.0/mlflow/permissions/experiments",
  ALL_MODELS: "/api/2.0/mlflow/permissions/registered-models",
  ALL_PROMPTS: "/api/2.0/mlflow/permissions/prompts",
  ALL_USERS: "/api/2.0/mlflow/users",

  // User management
  //   CREATE_USER: "/api/2.0/mlflow/users/create",
  //   GET_USER: "/api/2.0/mlflow/users/get",
  //   UPDATE_USER_PASSWORD: "/api/2.0/mlflow/users/update-password",
  //   UPDATE_USER_ADMIN: "/api/2.0/mlflow/users/update-admin",
  //   DELETE_USER: "/api/2.0/mlflow/users/delete",
  CREATE_ACCESS_TOKEN: "/api/2.0/mlflow/users/access-token",
  GET_CURRENT_USER: "/api/2.0/mlflow/permissions/users/current",
} as const;

export const DYNAMIC_API_ENDPOINTS = {
  //   // User permissions for resources
  //   USER_EXPERIMENT_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/users/${userName}/experiments",
  //   USER_EXPERIMENT_PERMISSION:
  //     "/api/2.0/mlflow/permissions/users/${userName}/experiments/${experimentId}",
  //   USER_REGISTERED_MODEL_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/users/${userName}/registered-models",
  //   USER_MODEL_PERMISSION:
  //     "/api/2.0/mlflow/permissions/users/${userName}/registered-models/${modelName}",
  //   USER_PROMPT_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/users/${userName}/prompts",
  //   USER_PROMPT_PERMISSION:
  //     "/api/2.0/mlflow/permissions/users/${userName}/prompts/${promptName}",

  // User pattern permissions
  //   USER_EXPERIMENT_PATTERN_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/users/${userName}/experiment-patterns",
  //   USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL:
  //     "/api/2.0/mlflow/permissions/users/${userName}/experiment-patterns/${patternId}",
  //   USER_REGISTERED_MODEL_PATTERN_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/users/${userName}/registered-models-patterns",
  //   USER_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL:
  //     "/api/2.0/mlflow/permissions/users/${userName}/registered-models-patterns/${patternId}",
  //   USER_PROMPT_PATTERN_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/users/${userName}/prompts-patterns",
  //   USER_PROMPT_PATTERN_PERMISSION_DETAIL:
  //     "/api/2.0/mlflow/permissions/users/${userName}/prompts-patterns/${patternId}",

  // Resource user permissions
  EXPERIMENT_USER_PERMISSIONS: (
    experimentId: DynamicPathParams["experimentId"]
  ) =>
    `/api/2.0/mlflow/permissions/experiments/${encodeURIComponent(
      String(experimentId)
    )}/users`,
  // REGISTERED_MODEL_USER_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/registered-models/${modelName}/users",
  //   PROMPT_USER_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/prompts/${promptName}/users",

  // Group permissions for resources
  //   GROUP_EXPERIMENT_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/experiments",
  //   GROUP_EXPERIMENT_PERMISSION_DETAIL:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/experiments/${experimentId}",
  //   GROUP_REGISTERED_MODEL_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/registered-models",
  //   GROUP_REGISTERED_MODEL_PERMISSION_DETAIL:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/registered-models/${modelName}",
  //   GROUP_PROMPT_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/prompts",
  //   GROUP_PROMPT_PERMISSION_DETAIL:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/prompts/${promptName}",

  // Group pattern permissions
  //   GROUP_EXPERIMENT_PATTERN_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/experiment-patterns",
  //   GROUP_EXPERIMENT_PATTERN_PERMISSION_DETAIL:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/experiment-patterns/${patternId}",
  //   GROUP_REGISTERED_MODEL_PATTERN_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/registered-models-patterns",
  //   GROUP_REGISTERED_MODEL_PATTERN_PERMISSION_DETAIL:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/registered-models-patterns/${patternId}",
  //   GROUP_PROMPT_PATTERN_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/prompts-patterns",
  //   GROUP_PROMPT_PATTERN_PERMISSION_DETAIL:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/prompts-patterns/${patternId}",

  // Resource group permissions
  //   EXPERIMENT_GROUP_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/experiments/${experimentId}/groups",
  //   REGISTERED_MODEL_GROUP_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/registered-models/${modelName}/groups",
  //   PROMPT_GROUP_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/prompts/${promptName}/groups",

  // Group user permissions
  //   GROUP_USER_PERMISSIONS:
  //     "/api/2.0/mlflow/permissions/groups/${groupName}/users",
} as const;

export type StaticEndpointKey = keyof typeof STATIC_API_ENDPOINTS;
export type DynamicEndpointKey = keyof typeof DYNAMIC_API_ENDPOINTS;

type DynamicEndpointFunction<K extends DynamicEndpointKey> =
  (typeof DYNAMIC_API_ENDPOINTS)[K];

export type PathParams<K extends DynamicEndpointKey> = Parameters<
  DynamicEndpointFunction<K>
>;
