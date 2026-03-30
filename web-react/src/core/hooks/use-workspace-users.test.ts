import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as useAuthModule from "./use-auth";
import * as workspaceService from "../services/workspace-service";
import { useWorkspaceUsers } from "./use-workspace-users";
import type { WorkspaceUserPermission } from "../../shared/types/entity";

vi.mock("./use-auth");
vi.mock("../services/workspace-service");

describe("useWorkspaceUsers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
  });

  it("returns empty array when workspace is undefined", async () => {
    const spy = vi.spyOn(workspaceService, "fetchWorkspaceUsers");

    const { result } = renderHook(() =>
      useWorkspaceUsers({ workspace: undefined }),
    );

    await waitFor(() => {
      expect(result.current.workspaceUsers).toEqual([]);
    });
    expect(spy).not.toHaveBeenCalled();
  });

  it("returns workspace users when workspace is provided", async () => {
    const mockUsers: WorkspaceUserPermission[] = [
      { workspace: "ws1", username: "user1", permission: "READ" },
      { workspace: "ws1", username: "user2", permission: "MANAGE" },
    ];
    vi.spyOn(workspaceService, "fetchWorkspaceUsers").mockResolvedValue(
      mockUsers,
    );

    const { result } = renderHook(() =>
      useWorkspaceUsers({ workspace: "ws1" }),
    );

    await waitFor(() => {
      expect(result.current.workspaceUsers).toEqual(mockUsers);
    });
  });

  it("passes through isLoading and error states", () => {
    vi.spyOn(workspaceService, "fetchWorkspaceUsers").mockImplementation(
      () => new Promise(() => {}), // never resolves
    );

    const { result } = renderHook(() =>
      useWorkspaceUsers({ workspace: "ws1" }),
    );

    expect(result.current.isLoading).toBeDefined();
    expect(result.current.error).toBeDefined();
    expect(result.current.refresh).toBeDefined();
  });
});
