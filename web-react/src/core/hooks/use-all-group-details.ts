import { fetchAllGroupDetails } from "../services/entity-service";
import type { GroupDetails } from "../../shared/types/entity";
import { useApi } from "./use-api";

/**
 * List groups with their external id and member count (admin-only endpoint).
 */
export function useAllGroupDetails() {
  const {
    data: groupDetails,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<GroupDetails[]>(fetchAllGroupDetails);

  return { groups: groupDetails ?? [], isLoading, error, refresh };
}
