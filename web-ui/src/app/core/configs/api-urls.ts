export const API_URL = {

  ALL_GROUPS: '/api/2.0/mlflow/permissions/groups',
  ALL_EXPERIMENTS: '/api/2.0/mlflow/permissions/experiments',
  ALL_MODELS: '/api/2.0/mlflow/permissions/registered-models',
  ALL_PROMPTS: '/api/2.0/mlflow/permissions/prompts',
  ALL_USERS: '/api/2.0/mlflow/permissions/users',

  USER_EXPERIMENT_PERMISSIONS: '/api/2.0/mlflow/permissions/users/${userName}/experiments',


  EXPERIMENTS_FOR_GROUP: '/api/2.0/mlflow/groups/${groupName}/experiments',
  USERS_FOR_EXPERIMENT: '/api/2.0/mlflow/experiments/${experimentName}/users',

  MODELS_FOR_GROUP: '/api/2.0/mlflow/groups/${groupName}/registered-models',
  MODELS_FOR_USER: '/api/2.0/mlflow/users/${userName}/registered-models',
  USERS_FOR_MODEL: '/api/2.0/mlflow/registered-models/${modelName}/users',

  PROMPTS_FOR_GROUP: '/api/2.0/mlflow/groups/${groupName}/prompts',
  PROMPTS_FOR_USER: '/api/2.0/mlflow/users/${userName}/prompts',
  USERS_FOR_PROMPT: '/api/2.0/mlflow/prompts/${promptName}/users',

  USER_EXPERIMENT_PERMISSION: '/api/2.0/mlflow/permissions/users/${userName}/experiments/${experimentId}',
  USER_MODEL_PERMISSION: '/api/2.0/mlflow/permissions/users/${userName}/registered-models/${modelName}',
  USER_PROMPT_PERMISSION: '/api/2.0/mlflow/permissions/users/${userName}/prompts/${promptName}',

  CREATE_USER: '/api/2.0/mlflow/users/create',
  DELETE_USER: '/api/2.0/mlflow/users/delete',
  CREATE_ACCESS_TOKEN: '/api/2.0/mlflow/users/access-token',
  GET_CURRENT_USER: '/api/2.0/mlflow/users/current',

  CREATE_GROUP_EXPERIMENT_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/experiments/create',
  DELETE_GROUP_EXPERIMENT_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/experiments/delete',
  UPDATE_GROUP_EXPERIMENT_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/experiments/update',

  CREATE_GROUP_MODEL_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/registered-models/create',
  DELETE_GROUP_MODEL_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/registered-models/delete',
  UPDATE_GROUP_MODEL_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/registered-models/update',

  CREATE_GROUP_PROMPT_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/prompts/create',
  DELETE_GROUP_PROMPT_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/prompts/delete',
  UPDATE_GROUP_PROMPT_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/prompts/update',


  CREATE_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/registered-models/regex-permissions/create',
  GET_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/registered-models/regex-permissions/get',
  UPDATE_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/registered-models/regex-permissions/update',
  DELETE_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/registered-models/regex-permissions/delete',

  CREATE_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/prompts/regex-permissions/create',
  GET_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/prompts/regex-permissions/get',
  UPDATE_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/prompts/regex-permissions/update',
  DELETE_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/prompts/regex-permissions/delete',

  USER_EXPERIMENT_PATTERN_PERMISSIONS: '/api/2.0/mlflow/permissions/users/${userName}/experiment-patterns',
  USER_EXPERIMENT_PATTERN_PERMISSION_DETAIL: '/api/2.0/mlflow/permissions/users/${userName}/experiment-patterns/${patternId}',
  // UPDATE_USER_EXPERIMENT_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/experiments/regex/update',
  // DELETE_USER_EXPERIMENT_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/experiments/regex/delete',

  CREATE_USER_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/registered-models/regex/create',
  GET_USER_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/registered-models/regex',
  UPDATE_USER_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/registered-models/regex/update',
  DELETE_USER_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/registered-models/regex/delete',

  CREATE_USER_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/prompts/regex/create',
  GET_USER_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/prompts/regex',
  UPDATE_USER_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/prompts/regex/update',
  DELETE_USER_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/users/${userName}/prompts/regex/delete',

  CREATE_GROUP_EXPERIMENT_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/experiments/regex/create',
  GET_GROUP_EXPERIMENT_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/experiments/regex',
  UPDATE_GROUP_EXPERIMENT_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/experiments/regex/update',
  DELETE_GROUP_EXPERIMENT_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/experiments/regex/delete',

  CREATE_GROUP_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/registered-models/regex/create',
  GET_GROUP_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/registered-models/regex',
  UPDATE_GROUP_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/registered-models/regex/update',
  DELETE_GROUP_REGISTERED_MODEL_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/registered-models/regex/delete',

  CREATE_GROUP_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/prompts/regex/create',
  GET_GROUP_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/prompts/regex',
  UPDATE_GROUP_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/prompts/regex/update',
  DELETE_GROUP_PROMPT_REGEX_PERMISSION: '/api/2.0/mlflow/groups/${groupName}/prompts/regex/delete',
};
