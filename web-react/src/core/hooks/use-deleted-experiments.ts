import { fetchDeletedExperimentsPage } from "../services/trash-service";
import { usePagedList } from "./use-paged-list";

/**
 * One page of deleted experiments, searched server-side on the experiment name.
 *
 * @param search - Submitted search term; changing it goes back to page 1.
 */
export function useDeletedExperiments(search = "") {
  const { items, total, pagination, isLoading, isFetching, error, refresh } =
    usePagedList(fetchDeletedExperimentsPage, search);

  return {
    deletedExperiments: items,
    total,
    pagination,
    isLoading,
    isFetching,
    error,
    refresh,
  };
}
