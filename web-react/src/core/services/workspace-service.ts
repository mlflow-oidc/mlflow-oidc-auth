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

export const createWorkspace = async (
  data: WorkspaceCrudCreateRequest,
): Promise<WorkspaceCrudResponse> => {
  return request<WorkspaceCrudResponse>(
    STATIC_API_ENDPOINTS.WORKSPACE_CRUD,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
};

export const updateWorkspace = async (
  workspace: string,
  data: WorkspaceCrudUpdateRequest,
): Promise<WorkspaceCrudResponse> => {
  return request<WorkspaceCrudResponse>(
    DYNAMIC_API_ENDPOINTS.WORKSPACE_CRUD_DETAIL(workspace),
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
  );
};

export const deleteWorkspace = async (workspace: string): Promise<void> => {
  return request<void>(
    DYNAMIC_API_ENDPOINTS.WORKSPACE_CRUD_DETAIL(workspace),
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
