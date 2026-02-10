import { createStaticApiFetcher } from "./create-api-fetcher";
import { request } from "./api-utils";
import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
} from "../configs/api-endpoints";
import type { DeletedExperiment, DeletedRun } from "../../shared/types/entity";

export const fetchDeletedExperiments = createStaticApiFetcher<{
  deleted_experiments: DeletedExperiment[];
}>({
  endpointKey: "TRASH_EXPERIMENTS",
  responseType: { deleted_experiments: [] } as {
    deleted_experiments: DeletedExperiment[];
  },
});

export const fetchDeletedRuns = createStaticApiFetcher<{
  deleted_runs: DeletedRun[];
}>({
  endpointKey: "TRASH_RUNS",
  responseType: { deleted_runs: [] } as {
    deleted_runs: DeletedRun[];
  },
});

export const cleanupTrash = async (params: {
  older_than?: string;
  run_ids?: string;
  experiment_ids?: string;
}) => {
  return request(STATIC_API_ENDPOINTS.TRASH_CLEANUP, {
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
