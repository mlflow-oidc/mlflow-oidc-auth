import {
  createStaticApiFetcher,
  createDynamicApiFetcher,
} from "./create-api-fetcher";
import { request } from "./api-utils";
import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
} from "../configs/api-endpoints";
import type {
  WorkspaceListResponse,
  WorkspaceUserPermission,
  WorkspaceGroupPermission,
  WorkspaceCrudCreateRequest,
  WorkspaceCrudUpdateRequest,
  WorkspaceCrudResponse,
  WorkspaceMemberCounts,
} from "../../shared/types/entity";

export const fetchAllWorkspaces =
  createStaticApiFetcher<WorkspaceListResponse>({
    endpointKey: "ALL_WORKSPACES",
    responseType: {} as WorkspaceListResponse,
  });

export const fetchWorkspaceUsers = createDynamicApiFetcher<
  WorkspaceUserPermission[],
  "WORKSPACE_USERS"
>({
  endpointKey: "WORKSPACE_USERS",
  responseType: [] as WorkspaceUserPermission[],
});

export const fetchWorkspaceGroups = createDynamicApiFetcher<
  WorkspaceGroupPermission[],
  "WORKSPACE_GROUPS"
>({
  endpointKey: "WORKSPACE_GROUPS",
  responseType: [] as WorkspaceGroupPermission[],
});

/** MLflow native workspace response wraps the object in a `workspace` key. */
type MlflowWorkspaceResponse = { workspace: WorkspaceCrudResponse };

export const createWorkspace = async (
  data: WorkspaceCrudCreateRequest,
): Promise<WorkspaceCrudResponse> => {
  const res = await request<MlflowWorkspaceResponse>(
    STATIC_API_ENDPOINTS.ALL_WORKSPACES,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
  return res.workspace;
};

export const updateWorkspace = async (
  workspace: string,
  data: WorkspaceCrudUpdateRequest,
): Promise<WorkspaceCrudResponse> => {
  const res = await request<MlflowWorkspaceResponse>(
    DYNAMIC_API_ENDPOINTS.WORKSPACE_DETAIL(workspace),
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
  );
  return res.workspace;
};

export const deleteWorkspace = async (workspace: string): Promise<void> => {
  await request<void>(
    DYNAMIC_API_ENDPOINTS.WORKSPACE_DETAIL(workspace),
    {
      method: "DELETE",
    },
  );
};

export const fetchWorkspaceMemberCounts = async (
  workspace: string,
  signal?: AbortSignal,
): Promise<WorkspaceMemberCounts> => {
  const [users, groups] = await Promise.all([
    fetchWorkspaceUsers(workspace, signal),
    fetchWorkspaceGroups(workspace, signal),
  ]);
  return { users: users.length, groups: groups.length };
};
