import { listScimTokens } from "../services/scim-token-service";
import type { ScimToken } from "../../../shared/types/scim";
import { useApi } from "../../../core/hooks/use-api";

export function useScimTokens() {
  const { data, isLoading, error, refetch } =
    useApi<ScimToken[]>(listScimTokens);

  return {
    tokens: data ?? [],
    isLoading,
    error,
    refresh: refetch,
  };
}
