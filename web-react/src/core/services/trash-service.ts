import { createStaticApiFetcher } from "./create-api-fetcher";
import { http } from "./http";
import { resolveUrl } from "./api-utils";
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
  const url = await resolveUrl(STATIC_API_ENDPOINTS.TRASH_CLEANUP, params);

  return http(url, {
    method: "POST",
  });
};

export const restoreExperiment = async (experimentId: string) => {
  const url = await resolveUrl(
    DYNAMIC_API_ENDPOINTS.RESTORE_EXPERIMENT(experimentId),
    {},
  );
  return http(url, {
    method: "POST",
  });
};

export const restoreRun = async (runId: string) => {
  const url = await resolveUrl(DYNAMIC_API_ENDPOINTS.RESTORE_RUN(runId), {});
  return http(url, {
    method: "POST",
  });
};
