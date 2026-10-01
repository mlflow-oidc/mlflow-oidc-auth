import { request } from "../../../core/services/api-utils";
import { DYNAMIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";

/** A `(provider, subject)` identity bound to a user. */
export type UserIdentity = { provider_id: string; subject: string };

export const listUserIdentities = async (
  username: string,
  signal?: AbortSignal,
): Promise<UserIdentity[]> =>
  request<UserIdentity[]>(DYNAMIC_API_ENDPOINTS.USER_IDENTITIES(username), {
    method: "GET",
    signal,
  });

/** Unbind one identity. The subject goes in the query string: it may contain "/". */
export const unbindUserIdentity = async (
  username: string,
  identity: UserIdentity,
): Promise<{ deleted: number }> => {
  const params = new URLSearchParams({
    provider_id: identity.provider_id,
    subject: identity.subject,
  });
  return request<{ deleted: number }>(
    `${DYNAMIC_API_ENDPOINTS.USER_IDENTITIES(username)}?${params.toString()}`,
    { method: "DELETE" },
  );
};
