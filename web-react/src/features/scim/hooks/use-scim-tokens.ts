import { fetchScimTokensPage } from "../services/scim-token-service";
import { usePagedList } from "../../../core/hooks/use-paged-list";

/** One page of SCIM bearer tokens (server-side pagination). */
export function useScimTokens() {
  const { items, total, pagination, isLoading, error, refresh } =
    usePagedList(fetchScimTokensPage);

  return {
    tokens: items,
    total,
    pagination,
    isLoading,
    error,
    refresh,
  };
}
