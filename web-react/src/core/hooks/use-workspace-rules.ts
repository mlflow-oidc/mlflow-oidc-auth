import type { WorkspaceRuleList } from "../../shared/types/entity";
import { fetchWorkspaceRules } from "../services/workspace-rule-service";
import { useApi } from "./use-api";

/** The workspace group rules and the server's permission ceiling (admin only). */
export function useWorkspaceRules() {
  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<WorkspaceRuleList>(fetchWorkspaceRules);

  return {
    rules: data?.rules ?? [],
    maxPermission: data?.max_permission ?? null,
    allowedPermissions: data?.allowed_permissions ?? [],
    isLoading,
    error,
    refresh,
  };
}
