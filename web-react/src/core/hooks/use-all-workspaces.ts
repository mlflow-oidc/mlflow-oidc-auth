import type {
  WorkspaceListItem,
  WorkspaceListResponse,
} from "../../shared/types/entity";
import { fetchAllWorkspaces } from "../services/workspace-service";
import { useApi } from "./use-api";

export function useAllWorkspaces() {
  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<WorkspaceListResponse>(fetchAllWorkspaces);
  const allWorkspaces: WorkspaceListItem[] | null =
    data?.workspaces ?? null;
  return { allWorkspaces, isLoading, error, refresh };
}
