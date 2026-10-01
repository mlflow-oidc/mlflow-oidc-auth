import { request } from "../../../core/services/api-utils";
import { DYNAMIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";

/** A way a service account can sign in: "internal" or an OIDC provider. */
export type ServiceAccountSource = {
  id: string;
  display_name: string;
  type: string;
};

export const INTERNAL_SOURCE = "internal";

export const fetchServiceAccountSources = (
  signal?: AbortSignal,
): Promise<ServiceAccountSource[]> =>
  request<ServiceAccountSource[]>(
    "/api/2.0/mlflow/users/service-account-sources",
    { method: "GET", signal },
  );

export const setServiceAccountSource = (
  username: string,
  source: string,
  subject?: string,
): Promise<{ username: string; service_account_source: string }> =>
  request(DYNAMIC_API_ENDPOINTS.USER_SERVICE_ACCOUNT_SOURCE(username), {
    method: "PUT",
    body: JSON.stringify(subject ? { source, subject } : { source }),
  });

/** How a source reads in a list: the provider's name, or what internal means. */
export function sourceLabel(
  source: string | null | undefined,
  sources: ServiceAccountSource[],
): string {
  if (!source || source === INTERNAL_SOURCE) return "Internal (tokens)";
  return sources.find((s) => s.id === source)?.display_name ?? source;
}
