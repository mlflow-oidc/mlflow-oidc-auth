import { createStaticApiFetcher } from "./create-api-fetcher";
import { request } from "./api-utils";
import { apiRequest } from "./typed-http";
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

// Workspace CRUD (`/api/3.0/mlflow/workspaces`) is MLflow's own API, proxied unchanged: it is not
// part of this plugin's contract, so those calls keep their hand-written types. The permission
// endpoints below are the plugin's and are typed from the generated contract.

export const fetchAllWorkspaces =
  createStaticApiFetcher<WorkspaceListResponse>({
    endpointKey: "ALL_WORKSPACES",
    responseType: {} as WorkspaceListResponse,
  });

export const fetchWorkspaceUsers = async (
  workspace: string,
  signal?: AbortSignal,
): Promise<WorkspaceUserPermission[]> =>
  (await apiRequest(
    "get",
    "/api/3.0/mlflow/permissions/workspaces/{workspace}/users",
    { path: { workspace }, signal },
  )) as WorkspaceUserPermission[];

export const fetchWorkspaceGroups = async (
  workspace: string,
  signal?: AbortSignal,
): Promise<WorkspaceGroupPermission[]> =>
  (await apiRequest(
    "get",
    "/api/3.0/mlflow/permissions/workspaces/{workspace}/groups",
    { path: { workspace }, signal },
  )) as WorkspaceGroupPermission[];

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
