import { useCallback } from "react";
import { useApi } from "../../../core/hooks/use-api";
import {
  listUserTokens,
  type TokenOwner,
} from "../services/user-token-service";
import type { UserToken } from "../../../shared/types/user";

/**
 * An account's API tokens.
 *
 * @param owner - The account, or `undefined` for the signed-in user.
 */
export function useUserTokens(owner: TokenOwner) {
  const fetcher = useCallback(
    (signal?: AbortSignal) => listUserTokens(owner, signal),
    [owner],
  );
  const { data, isLoading, error, refetch } = useApi<UserToken[]>(fetcher);

  return {
    tokens: data ?? [],
    isLoading,
    error,
    refresh: refetch,
  };
}
