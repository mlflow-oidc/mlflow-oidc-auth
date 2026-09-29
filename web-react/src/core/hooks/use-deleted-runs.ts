import { fetchDeletedRunsPage } from "../services/trash-service";
import { usePagedList } from "./use-paged-list";

/**
 * One page of deleted runs, searched server-side on the run name.
 *
 * @param search - Submitted search term; changing it goes back to page 1.
 */
export function useDeletedRuns(search = "") {
  const { items, total, pagination, isLoading, isFetching, error, refresh } =
    usePagedList(fetchDeletedRunsPage, search);

  return {
    deletedRuns: items,
    total,
    pagination,
    isLoading,
    isFetching,
    error,
    refresh,
  };
}
