import { request } from "./api-utils";
import { createPagedFetcher } from "./paged-list";
import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
} from "../configs/api-endpoints";
import type {
  CleanupTrashResponse,
  DeletedExperiment,
  DeletedRun,
} from "../../shared/types/entity";

/** Paginated deleted experiments; searched on the experiment name. */
export const fetchDeletedExperimentsPage = createPagedFetcher<
  { deleted_experiments?: DeletedExperiment[] },
  DeletedExperiment
>(STATIC_API_ENDPOINTS.TRASH_EXPERIMENTS, {
  extract: (body) => body?.deleted_experiments ?? [],
  displayKey: (experiment) => experiment.name,
});

/** Paginated deleted runs; searched on the run name. */
export const fetchDeletedRunsPage = createPagedFetcher<
  { deleted_runs?: DeletedRun[] },
  DeletedRun
>(STATIC_API_ENDPOINTS.TRASH_RUNS, {
  extract: (body) => body?.deleted_runs ?? [],
  displayKey: (run) => run.run_name || "",
});

export const cleanupTrash = async (params: {
  older_than?: string;
  run_ids?: string;
  experiment_ids?: string;
}) => {
  return request<CleanupTrashResponse>(STATIC_API_ENDPOINTS.TRASH_CLEANUP, {
    queryParams: params,
    method: "POST",
  });
};

export const restoreExperiment = async (experimentId: string) => {
  return request(DYNAMIC_API_ENDPOINTS.RESTORE_EXPERIMENT(experimentId), {
    method: "POST",
  });
};

export const restoreRun = async (runId: string) => {
  return request(DYNAMIC_API_ENDPOINTS.RESTORE_RUN(runId), {
    method: "POST",
  });
};
