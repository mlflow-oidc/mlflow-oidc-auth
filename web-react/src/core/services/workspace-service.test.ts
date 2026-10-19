import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchAllWorkspaces,
  fetchWorkspaceUsers,
  fetchWorkspaceGroups,
  createWorkspace,
  updateWorkspace,
  deleteWorkspace,
  fetchWorkspaceMemberCounts,
  grantWorkspaceUser,
  updateWorkspaceGroup,
  removeWorkspaceGroup,
} from "./workspace-service";

vi.mock("./api-utils", () => ({
  request: vi.fn(),
}));

import { request } from "./api-utils";

const mockRequest = vi.mocked(request);

describe("workspace-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("exports fetchAllWorkspaces as a function", () => {
    expect(typeof fetchAllWorkspaces).toBe("function");
  });

  it("exports fetchWorkspaceUsers as a function", () => {
    expect(typeof fetchWorkspaceUsers).toBe("function");
  });

  it("exports fetchWorkspaceGroups as a function", () => {
    expect(typeof fetchWorkspaceGroups).toBe("function");
  });

  describe("createWorkspace", () => {
    it("calls request with correct endpoint and body", async () => {
      const mockMlflowResponse = {
        workspace: {
          name: "test-ws",
          description: "A test workspace",
          default_artifact_root: null,
        },
      };
      mockRequest.mockResolvedValue(mockMlflowResponse);

      const result = await createWorkspace({
        name: "test-ws",
        description: "A test workspace",
      });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces",
        {
          method: "POST",
          body: JSON.stringify({
            name: "test-ws",
            description: "A test workspace",
          }),
        },
      );
      expect(result).toEqual({
        name: "test-ws",
        description: "A test workspace",
        default_artifact_root: null,
      });
    });

    it("calls request without description when not provided", async () => {
      mockRequest.mockResolvedValue({
        workspace: {
          name: "minimal-ws",
          description: "",
          default_artifact_root: null,
        },
      });

      await createWorkspace({ name: "minimal-ws" });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces",
        {
          method: "POST",
          body: JSON.stringify({ name: "minimal-ws" }),
        },
      );
    });

    it("passes default_artifact_root when provided", async () => {
      mockRequest.mockResolvedValue({
        workspace: {
          name: "test-ws",
          description: "",
          default_artifact_root: "s3://my-bucket",
        },
      });

      await createWorkspace({
        name: "test-ws",
        default_artifact_root: "s3://my-bucket",
      });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces",
        {
          method: "POST",
          body: JSON.stringify({
            name: "test-ws",
            default_artifact_root: "s3://my-bucket",
          }),
        },
      );
    });
  });

  describe("updateWorkspace", () => {
    it("calls request with correct endpoint and body", async () => {
      const mockMlflowResponse = {
        workspace: {
          name: "test-ws",
          description: "Updated description",
          default_artifact_root: null,
        },
      };
      mockRequest.mockResolvedValue(mockMlflowResponse);

      const result = await updateWorkspace("test-ws", {
        description: "Updated description",
      });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/test-ws",
        {
          method: "PATCH",
          body: JSON.stringify({ description: "Updated description" }),
        },
      );
      expect(result).toEqual({
        name: "test-ws",
        description: "Updated description",
        default_artifact_root: null,
      });
    });

    it("encodes workspace name in URL", async () => {
      mockRequest.mockResolvedValue({
        workspace: {
          name: "ws name",
          description: "",
          default_artifact_root: null,
        },
      });

      await updateWorkspace("ws name", { description: "desc" });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/ws%20name",
        expect.objectContaining({ method: "PATCH" }),
      );
    });

    it("passes default_artifact_root when provided", async () => {
      mockRequest.mockResolvedValue({
        workspace: {
          name: "test-ws",
          description: "desc",
          default_artifact_root: "s3://new-bucket",
        },
      });

      await updateWorkspace("test-ws", {
        description: "desc",
        default_artifact_root: "s3://new-bucket",
      });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/test-ws",
        {
          method: "PATCH",
          body: JSON.stringify({
            description: "desc",
            default_artifact_root: "s3://new-bucket",
          }),
        },
      );
    });
  });

  describe("deleteWorkspace", () => {
    it("calls request with correct endpoint and DELETE method", async () => {
      mockRequest.mockResolvedValue(undefined);

      await deleteWorkspace("test-ws");

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/test-ws",
        {
          method: "DELETE",
        },
      );
    });
  });

  describe("fetchWorkspaceUsers / fetchWorkspaceGroups", () => {
    it("keeps a grant whose permission is not a level, raw value intact", async () => {
      const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
      mockRequest.mockResolvedValue([
        { workspace: "ws1", username: "a", permission: "READ" },
        { workspace: "ws1", username: "b", permission: "OWNER" },
      ]);

      const users = await fetchWorkspaceUsers("ws1");

      expect(users.map((u) => [u.username, u.permission])).toEqual([
        ["a", "READ"],
        ["b", "OWNER"],
      ]);
      warn.mockRestore();
    });

    it("calls the typed workspace grant endpoints", async () => {
      mockRequest.mockResolvedValue({});
      await grantWorkspaceUser("ws 1", "a@b", "EDIT");
      await updateWorkspaceGroup("ws 1", "g/1", "READ");
      await removeWorkspaceGroup("ws 1", "g/1");

      expect(mockRequest).toHaveBeenNthCalledWith(
        1,
        "/api/3.0/mlflow/permissions/workspaces/ws%201/users",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ username: "a@b", permission: "EDIT" }),
        }),
      );
      expect(mockRequest).toHaveBeenNthCalledWith(
        2,
        "/api/3.0/mlflow/permissions/workspaces/ws%201/groups/g%2F1",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ group_name: "g/1", permission: "READ" }),
        }),
      );
      expect(mockRequest).toHaveBeenNthCalledWith(
        3,
        "/api/3.0/mlflow/permissions/workspaces/ws%201/groups/g%2F1",
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  describe("fetchWorkspaceMemberCounts", () => {
    it("returns combined user and group counts", async () => {
      // fetchWorkspaceUsers and fetchWorkspaceGroups use createDynamicApiFetcher
      // which internally calls request. We need to mock at the module level.
      // Instead, we test via the public API by mocking the underlying fetchers.

      // Mock request to respond differently based on the URL
      mockRequest.mockImplementation((endpoint: string) => {
        if (endpoint.includes("/users")) {
          return Promise.resolve([
            {
              workspace: "ws1",
              username: "user1",
              permission: "READ",
            },
            {
              workspace: "ws1",
              username: "user2",
              permission: "MANAGE",
            },
          ]);
        }
        if (endpoint.includes("/groups")) {
          return Promise.resolve([
            {
              workspace: "ws1",
              group_name: "group1",
              permission: "READ",
            },
          ]);
        }
        return Promise.resolve([]);
      });

      const result = await fetchWorkspaceMemberCounts("ws1");

      expect(result).toEqual({ users: 2, groups: 1 });
    });

    it("counts rows without checking their permissions", async () => {
      const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
      mockRequest.mockImplementation((endpoint: string) =>
        Promise.resolve(
          endpoint.includes("/users")
            ? [{ workspace: "ws1", username: "u", permission: "OWNER" }]
            : [{ workspace: "ws1", group_name: "g", permission: "SUPER" }],
        ),
      );

      await expect(fetchWorkspaceMemberCounts("ws1")).resolves.toEqual({
        users: 1,
        groups: 1,
      });
      expect(warn).not.toHaveBeenCalled();
      warn.mockRestore();
    });

    it("returns zero counts for workspace with no members", async () => {
      mockRequest.mockResolvedValue([]);

      const result = await fetchWorkspaceMemberCounts("empty-ws");

      expect(result).toEqual({ users: 0, groups: 0 });
    });
  });
});
