import {
  createStaticApiFetcher,
  createDynamicApiFetcher,
} from "./create-api-fetcher.ts";
import type {
  EntityPermission,
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
