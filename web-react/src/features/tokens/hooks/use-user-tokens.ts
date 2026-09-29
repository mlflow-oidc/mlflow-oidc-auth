import { useCallback } from "react";
import { usePagedList } from "../../../core/hooks/use-paged-list";
import type { ListQuery } from "../../../core/services/paged-list";
import {
  listUserTokensPage,
  type TokenOwner,
} from "../services/user-token-service";

/**
 * One page of an account's API tokens, searched server-side on the token name.
 *
 * @param owner - The account, or `undefined` for the signed-in user.
 * @param search - Submitted search term; changing it goes back to page 1.
 */
export function useUserTokens(owner: TokenOwner, search = "") {
  const fetchPage = useCallback(
    (query: ListQuery, signal?: AbortSignal) =>
      listUserTokensPage(owner, query, signal),
    [owner],
  );
  const { items, total, pagination, isLoading, isFetching, error, refresh } =
    usePagedList(fetchPage, search);

  return {
    tokens: items,
    total,
    pagination,
    isLoading,
    isFetching,
    error,
    refresh,
  };
}
