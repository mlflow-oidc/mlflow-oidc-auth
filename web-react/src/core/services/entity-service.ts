import { createApiFetcher } from "./api-utils";
import type {
  ExperimentListItem,
  ModelListItem,
  PromptListItem,
} from "../../shared/types/entity";

export const fetchAllGroups = createApiFetcher<string[]>({
  endpointKey: "ALL_GROUPS",
  responseType: [] as string[],
});

export const fetchAllExperiments = createApiFetcher<ExperimentListItem[]>({
  endpointKey: "ALL_EXPERIMENTS",
  responseType: [] as ExperimentListItem[],
});

export const fetchAllModels = createApiFetcher<ModelListItem[]>({
  endpointKey: "ALL_MODELS",
  responseType: [] as ModelListItem[],
});

export const fetchAllPrompts = createApiFetcher<PromptListItem[]>({
  endpointKey: "ALL_PROMPTS",
  responseType: [] as PromptListItem[],
});
