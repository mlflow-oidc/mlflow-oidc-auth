import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as useAuthModule from "./use-auth";
import * as workspaceService from "../services/workspace-service";
import { useWorkspaceGroups } from "./use-workspace-groups";
import type { WorkspaceGroupPermission } from "../../shared/types/entity";

vi.mock("./use-auth");
vi.mock("../services/workspace-service");

describe("useWorkspaceGroups", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
  });

  it("returns empty array when workspace is undefined", async () => {
    const spy = vi.spyOn(workspaceService, "fetchWorkspaceGroups");

    const { result } = renderHook(() =>
      useWorkspaceGroups({ workspace: undefined }),
    );

    await waitFor(() => {
      expect(result.current.workspaceGroups).toEqual([]);
    });
    expect(spy).not.toHaveBeenCalled();
  });

  it("returns workspace groups when workspace is provided", async () => {
    const mockGroups: WorkspaceGroupPermission[] = [
      { workspace: "ws1", group_name: "team-a", permission: "READ" },
      { workspace: "ws1", group_name: "team-b", permission: "MANAGE" },
    ];
    vi.spyOn(workspaceService, "fetchWorkspaceGroups").mockResolvedValue(
      mockGroups,
    );

    const { result } = renderHook(() =>
      useWorkspaceGroups({ workspace: "ws1" }),
    );

    await waitFor(() => {
      expect(result.current.workspaceGroups).toEqual(mockGroups);
    });
  });

  it("passes through isLoading and error states", () => {
    vi.spyOn(workspaceService, "fetchWorkspaceGroups").mockImplementation(
      () => new Promise(() => {}), // never resolves
    );

    const { result } = renderHook(() =>
      useWorkspaceGroups({ workspace: "ws1" }),
    );

    expect(result.current.isLoading).toBeDefined();
    expect(result.current.error).toBeDefined();
    expect(result.current.refresh).toBeDefined();
  });
});
