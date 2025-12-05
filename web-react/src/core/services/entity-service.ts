import { http } from "./http";
import { getRuntimeConfig } from "../../shared/services/runtime-config";
import { API_ENDPOINTS } from "../configs/api-endpoints";
import type {
  ExperimentListItem,
  ModelListItem,
  PromptListItem,
} from "../../shared/types/entity";

export async function fetchAllGroups(signal?: AbortSignal): Promise<string[]> {
  const cfg = await getRuntimeConfig(signal);
  const url = `${cfg.basePath}${API_ENDPOINTS.ALL_GROUPS}`;
  return http<string[]>(url, { method: "GET", signal });
}

export async function fetchAllExperiments(
  signal?: AbortSignal
): Promise<ExperimentListItem[]> {
  const cfg = await getRuntimeConfig(signal);
  const url = `${cfg.basePath}${API_ENDPOINTS.ALL_EXPERIMENTS}`;
  return http<ExperimentListItem[]>(url, { method: "GET", signal });
}

export async function fetchAllModels(
  signal?: AbortSignal
): Promise<ModelListItem[]> {
  const cfg = await getRuntimeConfig(signal);
  const url = `${cfg.basePath}${API_ENDPOINTS.ALL_MODELS}`;
  return http<ModelListItem[]>(url, { method: "GET", signal });
}

export async function fetchAllPrompts(
  signal?: AbortSignal
): Promise<PromptListItem[]> {
  const cfg = await getRuntimeConfig(signal);
  const url = `${cfg.basePath}${API_ENDPOINTS.ALL_PROMPTS}`;
  return http<PromptListItem[]>(url, { method: "GET", signal });
}
