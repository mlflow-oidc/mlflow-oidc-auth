import { createStaticApiFetcher } from "./create-api-fetcher";
import { request } from "./api-utils";
import { apiRequest } from "./typed-http";
import { withPermissionLevels } from "../../shared/utils/permission-level";
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
  PermissionLevel,
} from "../../shared/types/entity";

// Workspace CRUD (`/api/3.0/mlflow/workspaces`) is MLflow's own API, proxied unchanged: it is not
// part of this plugin's contract, so those calls keep their hand-written types. The permission
// endpoints below are the plugin's and are typed from the generated contract.

export const fetchAllWorkspaces = createStaticApiFetcher<WorkspaceListResponse>(
  {
    endpointKey: "ALL_WORKSPACES",
    responseType: {} as WorkspaceListResponse,
  },
);

export const fetchWorkspaceUsers = async (
  workspace: string,
  signal?: AbortSignal,
): Promise<WorkspaceUserPermission[]> =>
  withPermissionLevels(
    await apiRequest(
      "get",
      "/api/3.0/mlflow/permissions/workspaces/{workspace}/users",
      { path: { workspace }, signal },
    ),
    "the workspace users list",
  );

/** Grant a user a permission on a workspace. */
export const grantWorkspaceUser = (
  workspace: string,
  username: string,
  permission: PermissionLevel,
) =>
  apiRequest(
    "post",
    "/api/3.0/mlflow/permissions/workspaces/{workspace}/users",
    { path: { workspace }, body: { username, permission } },
  );

/** Change a user's permission on a workspace. */
export const updateWorkspaceUser = (
  workspace: string,
  username: string,
  permission: PermissionLevel,
) =>
  apiRequest(
    "patch",
    "/api/3.0/mlflow/permissions/workspaces/{workspace}/users/{username}",
    { path: { workspace, username }, body: { username, permission } },
  );

/** Remove a user's permission on a workspace. */
export const removeWorkspaceUser = (workspace: string, username: string) =>
  apiRequest(
    "delete",
    "/api/3.0/mlflow/permissions/workspaces/{workspace}/users/{username}",
    { path: { workspace, username } },
  );

/** Grant a group a permission on a workspace. */
export const grantWorkspaceGroup = (
  workspace: string,
  group_name: string,
  permission: PermissionLevel,
) =>
  apiRequest(
    "post",
    "/api/3.0/mlflow/permissions/workspaces/{workspace}/groups",
    { path: { workspace }, body: { group_name, permission } },
  );

/** Change a group's permission on a workspace. */
export const updateWorkspaceGroup = (
  workspace: string,
  group_name: string,
  permission: PermissionLevel,
) =>
  apiRequest(
    "patch",
    "/api/3.0/mlflow/permissions/workspaces/{workspace}/groups/{group_name}",
    { path: { workspace, group_name }, body: { group_name, permission } },
  );

/** Remove a group's permission on a workspace. */
export const removeWorkspaceGroup = (workspace: string, group_name: string) =>
  apiRequest(
    "delete",
    "/api/3.0/mlflow/permissions/workspaces/{workspace}/groups/{group_name}",
    { path: { workspace, group_name } },
  );

export const fetchWorkspaceGroups = async (
  workspace: string,
  signal?: AbortSignal,
): Promise<WorkspaceGroupPermission[]> =>
  withPermissionLevels(
    await apiRequest(
      "get",
      "/api/3.0/mlflow/permissions/workspaces/{workspace}/groups",
      { path: { workspace }, signal },
    ),
    "the workspace groups list",
  );

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
  await request<void>(DYNAMIC_API_ENDPOINTS.WORKSPACE_DETAIL(workspace), {
    method: "DELETE",
  });
};

export const fetchWorkspaceMemberCounts = async (
  workspace: string,
  signal?: AbortSignal,
): Promise<WorkspaceMemberCounts> => {
  // Counting needs no permission values, so the rows are not checked: an unexpected value in
  // one grant must not cost the workspace list its member counts.
  const [users, groups] = await Promise.all([
    apiRequest(
      "get",
      "/api/3.0/mlflow/permissions/workspaces/{workspace}/users",
      { path: { workspace }, signal },
    ),
    apiRequest(
      "get",
      "/api/3.0/mlflow/permissions/workspaces/{workspace}/groups",
      { path: { workspace }, signal },
    ),
  ]);
  return { users: users.length, groups: groups.length };
};
