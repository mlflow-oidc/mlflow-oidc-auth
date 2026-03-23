import {
  createStaticApiFetcher,
  createDynamicApiFetcher,
} from "./create-api-fetcher";
import type {
  WorkspaceListResponse,
  WorkspaceUserPermission,
  WorkspaceGroupPermission,
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
