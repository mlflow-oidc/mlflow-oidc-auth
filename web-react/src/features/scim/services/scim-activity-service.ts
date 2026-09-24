import { request } from "../../../core/services/api-utils";
import { STATIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";
import { createStaticApiFetcher } from "../../../core/services/create-api-fetcher";
import type {
  ScimActivityPage,
  ScimActivityQuery,
  ScimProvisioningStatus,
} from "../../../shared/types/scim";

export const fetchScimStatus = createStaticApiFetcher<ScimProvisioningStatus>(
  {
    endpointKey: "SCIM_STATUS",
  },
);

export const fetchScimActivity = async (
  query: ScimActivityQuery = {},
  signal?: AbortSignal,
): Promise<ScimActivityPage> => {
  return request<ScimActivityPage>(STATIC_API_ENDPOINTS.SCIM_ACTIVITY, {
    method: "GET",
    signal,
    queryParams: {
      limit: query.limit,
      before: query.before,
      outcome: query.outcome,
      token_id: query.token_id,
    },
  });
};
