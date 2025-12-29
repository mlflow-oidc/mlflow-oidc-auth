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
  "USER_REGISTERED_MODEL_PERMISSIONS"
>({
  endpointKey: "USER_REGISTERED_MODEL_PERMISSIONS",
  responseType: [] as ModelPermission[],
});

export const fetchUserPromptPermissions = createDynamicApiFetcher<
  PromptPermission[],
  "USER_PROMPT_PERMISSIONS"
>({
  endpointKey: "USER_PROMPT_PERMISSIONS",
  responseType: [] as PromptPermission[],
});

export const fetchModelUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "REGISTERED_MODEL_USER_PERMISSIONS"
>({
  endpointKey: "REGISTERED_MODEL_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchPromptUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "PROMPT_USER_PERMISSIONS"
>({
  endpointKey: "PROMPT_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});
