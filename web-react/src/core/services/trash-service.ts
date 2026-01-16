import { createStaticApiFetcher } from "./create-api-fetcher";
import { http } from "./http";
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

export const fetchDeletedRuns = createStaticApiFetcher<DeletedRun[]>({
  endpointKey: "TRASH_RUNS",
  responseType: [] as DeletedRun[],
});

export const cleanupTrash = async (params: {
  older_than?: string;
  run_ids?: string;
  experiment_ids?: string;
}) => {
  const searchParams = new URLSearchParams();
  if (params.older_than) searchParams.append("older_than", params.older_than);
  if (params.run_ids) searchParams.append("run_ids", params.run_ids);
  if (params.experiment_ids)
    searchParams.append("experiment_ids", params.experiment_ids);

  const queryString = searchParams.toString();
  const url = `${STATIC_API_ENDPOINTS.TRASH_CLEANUP}${
    queryString ? `?${queryString}` : ""
  }`;

  return http(url, {
    method: "POST",
  });
};

export const restoreExperiment = async (experimentId: string) => {
  return http(DYNAMIC_API_ENDPOINTS.RESTORE_EXPERIMENT(experimentId), {
    method: "POST",
  });
};

export const restoreRun = async (runId: string) => {
  return http(DYNAMIC_API_ENDPOINTS.RESTORE_RUN(runId), {
    method: "POST",
  });
};
