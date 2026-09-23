import { useCallback, useMemo, useState } from "react";
import { fetchAllUserDetails } from "../services/user-service";
import type { UserDetails } from "../../shared/types/user";
import { useApi } from "./use-api";

/**
 * List users with their lifecycle state (admin-only endpoint).
 *
 * `service` mirrors the backend's `?service=` filter: omitted returns both
 * users and service accounts, `false` returns users only, `true` returns
 * service accounts only.
 *
 * `updateLocalUser` applies an optimistic patch (e.g. after an
 * activate/deactivate call) without waiting for a full refetch;
 * `refresh` clears any local overrides and refetches from the server.
 */
export function useAllUserDetails(service?: boolean) {
  const fetcher = useMemo(
    () => fetchAllUserDetails(service),
    [service],
  );

  const {
    data: response,
    isLoading,
    error,
    refetch,
  } = useApi<UserDetails[]>(fetcher);

  const [localOverrides, setLocalOverrides] = useState<
    Map<string, Partial<UserDetails>>
  >(() => new Map());

  const users = (response ?? []).map((u) => {
    const overrides = localOverrides.get(u.username);
    return overrides ? { ...u, ...overrides } : u;
  });

  const refresh = useCallback(() => {
    setLocalOverrides(new Map());
    refetch();
  }, [refetch]);

  const updateLocalUser = useCallback(
    (username: string, patch: Partial<UserDetails>) => {
      setLocalOverrides((prev) => new Map(prev).set(username, patch));
    },
    [],
  );

  return { users, isLoading, error, refresh, updateLocalUser };
}
