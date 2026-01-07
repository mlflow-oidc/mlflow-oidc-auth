import {
  createStaticApiFetcher,
  createDynamicApiFetcher,
} from "./create-api-fetcher.ts";
import type {
  EntityPermission,
  ExperimentPermission,
  ModelPermission,
  PromptPermission,
  ExperimentListItem,
  ModelListItem,
  PromptListItem,
  ExperimentPatternPermission,
  ModelPatternPermission,
  PromptPatternPermission,
} from "../../shared/types/entity";

export const fetchAllGroups = createStaticApiFetcher<string[]>({
  endpointKey: "ALL_GROUPS",
  responseType: [] as string[],
});

export const fetchAllExperiments = createStaticApiFetcher<ExperimentListItem[]>(
  {
    endpointKey: "ALL_EXPERIMENTS",
    responseType: [] as ExperimentListItem[],
  }
);

export const fetchAllModels = createStaticApiFetcher<ModelListItem[]>({
  endpointKey: "ALL_MODELS",
  responseType: [] as ModelListItem[],
});

export const fetchAllPrompts = createStaticApiFetcher<PromptListItem[]>({
  endpointKey: "ALL_PROMPTS",
  responseType: [] as PromptListItem[],
});

export const fetchExperimentUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "EXPERIMENT_USER_PERMISSIONS"
>({
  endpointKey: "EXPERIMENT_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchUserExperimentPermissions = createDynamicApiFetcher<
  ExperimentPermission[],
  "USER_EXPERIMENT_PERMISSIONS"
>({
  endpointKey: "USER_EXPERIMENT_PERMISSIONS",
  responseType: [] as ExperimentPermission[],
});

export const fetchUserRegisteredModelPermissions = createDynamicApiFetcher<
  ModelPermission[],
  "USER_MODEL_PERMISSIONS"
>({
  endpointKey: "USER_MODEL_PERMISSIONS",
  responseType: [] as ModelPermission[],
});

export const fetchUserPromptPermissions = createDynamicApiFetcher<
  PromptPermission[],
  "USER_PROMPT_PERMISSIONS"
>({
  endpointKey: "USER_PROMPT_PERMISSIONS",
  responseType: [] as PromptPermission[],
});

// User pattern permission fetchers
export const fetchUserExperimentPatternPermissions = createDynamicApiFetcher<
  ExperimentPatternPermission[],
  "USER_EXPERIMENT_PATTERN_PERMISSIONS"
>({
  endpointKey: "USER_EXPERIMENT_PATTERN_PERMISSIONS",
  responseType: [] as ExperimentPatternPermission[],
});

export const fetchUserModelPatternPermissions = createDynamicApiFetcher<
  ModelPatternPermission[],
  "USER_MODEL_PATTERN_PERMISSIONS"
>({
  endpointKey: "USER_MODEL_PATTERN_PERMISSIONS",
  responseType: [] as ModelPatternPermission[],
});

export const fetchUserPromptPatternPermissions = createDynamicApiFetcher<
  PromptPatternPermission[],
  "USER_PROMPT_PATTERN_PERMISSIONS"
>({
  endpointKey: "USER_PROMPT_PATTERN_PERMISSIONS",
  responseType: [] as PromptPatternPermission[],
});

export const fetchModelUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "MODEL_USER_PERMISSIONS"
>({
  endpointKey: "MODEL_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchPromptUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "PROMPT_USER_PERMISSIONS"
>({
  endpointKey: "PROMPT_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchGroupExperimentPermissions = createDynamicApiFetcher<
  ExperimentPermission[],
  "GROUP_EXPERIMENT_PERMISSIONS"
>({
  endpointKey: "GROUP_EXPERIMENT_PERMISSIONS",
  responseType: [] as ExperimentPermission[],
});

export const fetchGroupRegisteredModelPermissions = createDynamicApiFetcher<
  ModelPermission[],
  "GROUP_MODEL_PERMISSIONS"
>({
  endpointKey: "GROUP_MODEL_PERMISSIONS",
  responseType: [] as ModelPermission[],
});

export const fetchGroupPromptPermissions = createDynamicApiFetcher<
  PromptPermission[],
  "GROUP_PROMPT_PERMISSIONS"
>({
  endpointKey: "GROUP_PROMPT_PERMISSIONS",
  responseType: [] as PromptPermission[],
});

export const fetchExperimentGroupPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "EXPERIMENT_GROUP_PERMISSIONS"
>({
  endpointKey: "EXPERIMENT_GROUP_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchModelGroupPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "MODEL_GROUP_PERMISSIONS"
>({
  endpointKey: "MODEL_GROUP_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchPromptGroupPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "PROMPT_GROUP_PERMISSIONS"
>({
  endpointKey: "PROMPT_GROUP_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

// Group pattern permission fetchers
export const fetchGroupExperimentPatternPermissions = createDynamicApiFetcher<
  ExperimentPatternPermission[],
  "GROUP_EXPERIMENT_PATTERN_PERMISSIONS"
>({
  endpointKey: "GROUP_EXPERIMENT_PATTERN_PERMISSIONS",
  responseType: [] as ExperimentPatternPermission[],
});

export const fetchGroupModelPatternPermissions = createDynamicApiFetcher<
  ModelPatternPermission[],
  "GROUP_MODEL_PATTERN_PERMISSIONS"
>({
  endpointKey: "GROUP_MODEL_PATTERN_PERMISSIONS",
  responseType: [] as ModelPatternPermission[],
});

export const fetchGroupPromptPatternPermissions = createDynamicApiFetcher<
  PromptPatternPermission[],
  "GROUP_PROMPT_PATTERN_PERMISSIONS"
>({
  endpointKey: "GROUP_PROMPT_PATTERN_PERMISSIONS",
  responseType: [] as PromptPatternPermission[],
});
