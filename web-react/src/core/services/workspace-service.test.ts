import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchAllWorkspaces,
  fetchWorkspaceUsers,
  fetchWorkspaceGroups,
  createWorkspace,
  updateWorkspace,
  deleteWorkspace,
  fetchWorkspaceMemberCounts,
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
      const mockResponse = {
        name: "test-ws",
        description: "A test workspace",
        default_artifact_root: null,
      };
      mockRequest.mockResolvedValue(mockResponse);

      const result = await createWorkspace({
        name: "test-ws",
        description: "A test workspace",
      });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/crud",
        {
          method: "POST",
          body: JSON.stringify({
            name: "test-ws",
            description: "A test workspace",
          }),
        },
      );
      expect(result).toEqual(mockResponse);
    });

    it("calls request without description when not provided", async () => {
      mockRequest.mockResolvedValue({
        name: "minimal-ws",
        description: "",
        default_artifact_root: null,
      });

      await createWorkspace({ name: "minimal-ws" });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/crud",
        {
          method: "POST",
          body: JSON.stringify({ name: "minimal-ws" }),
        },
      );
    });

    it("passes default_artifact_root when provided", async () => {
      mockRequest.mockResolvedValue({
        name: "test-ws",
        description: "",
        default_artifact_root: "s3://my-bucket",
      });

      await createWorkspace({
        name: "test-ws",
        default_artifact_root: "s3://my-bucket",
      });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/crud",
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
      const mockResponse = {
        name: "test-ws",
        description: "Updated description",
        default_artifact_root: null,
      };
      mockRequest.mockResolvedValue(mockResponse);

      const result = await updateWorkspace("test-ws", {
        description: "Updated description",
      });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/crud/test-ws",
        {
          method: "PATCH",
          body: JSON.stringify({ description: "Updated description" }),
        },
      );
      expect(result).toEqual(mockResponse);
    });

    it("encodes workspace name in URL", async () => {
      mockRequest.mockResolvedValue({
        name: "ws name",
        description: "",
        default_artifact_root: null,
      });

      await updateWorkspace("ws name", { description: "desc" });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/crud/ws%20name",
        expect.objectContaining({ method: "PATCH" }),
      );
    });

    it("passes default_artifact_root when provided", async () => {
      mockRequest.mockResolvedValue({
        name: "test-ws",
        description: "desc",
        default_artifact_root: "s3://new-bucket",
      });

      await updateWorkspace("test-ws", {
        description: "desc",
        default_artifact_root: "s3://new-bucket",
      });

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/workspaces/crud/test-ws",
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
        "/api/3.0/mlflow/workspaces/crud/test-ws",
        {
          method: "DELETE",
        },
      );
    });
  });

  describe("fetchWorkspaceMemberCounts", () => {
    it("returns combined user and group counts", async () => {
      // fetchWorkspaceUsers and fetchWorkspaceGroups use createDynamicApiFetcher
      // which internally calls request. We need to mock at the module level.
      // Instead, we test via the public API by mocking the underlying fetchers.

      // Mock request to respond differently based on the URL
      mockRequest.mockImplementation(async (endpoint: string) => {
        if (endpoint.includes("/users")) {
          return [
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
          ];
        }
        if (endpoint.includes("/groups")) {
          return [
            {
              workspace: "ws1",
              group_name: "group1",
              permission: "READ",
            },
          ];
        }
        return [];
      });

      const result = await fetchWorkspaceMemberCounts("ws1");

      expect(result).toEqual({ users: 2, groups: 1 });
    });

    it("returns zero counts for workspace with no members", async () => {
      mockRequest.mockResolvedValue([]);

      const result = await fetchWorkspaceMemberCounts("empty-ws");

      expect(result).toEqual({ users: 0, groups: 0 });
    });
  });
});
