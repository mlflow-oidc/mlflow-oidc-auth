import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as useAuthModule from "./use-auth";
import * as workspaceService from "../services/workspace-service";
import { useAllWorkspaces } from "./use-all-workspaces";
import type {
  WorkspaceListItem,
  WorkspaceListResponse,
} from "../../shared/types/entity";

vi.mock("./use-auth");
vi.mock("../services/workspace-service");

describe("useAllWorkspaces", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
  });

  it("returns allWorkspaces as null when useApi returns null data", () => {
    vi.spyOn(workspaceService, "fetchAllWorkspaces").mockResolvedValue(
      undefined as unknown as WorkspaceListResponse,
    );

    const { result } = renderHook(() => useAllWorkspaces());

    // Initially data is null (loading)
    expect(result.current.allWorkspaces).toBeNull();
  });

  it("unwraps workspaces array from response object", async () => {
    const mockWorkspaces: WorkspaceListItem[] = [
      {
        name: "workspace-1",
        description: "First workspace",
        default_artifact_root: "/artifacts/ws1",
      },
      {
        name: "workspace-2",
        description: "Second workspace",
        default_artifact_root: "/artifacts/ws2",
      },
    ];
    const mockResponse: WorkspaceListResponse = {
      workspaces: mockWorkspaces,
    };
    vi.spyOn(workspaceService, "fetchAllWorkspaces").mockResolvedValue(
      mockResponse,
    );

    const { result } = renderHook(() => useAllWorkspaces());

    await waitFor(() => {
      expect(result.current.allWorkspaces).toEqual(mockWorkspaces);
    });
  });

  it("passes through isLoading and error states", () => {
    vi.spyOn(workspaceService, "fetchAllWorkspaces").mockImplementation(
      () => new Promise(() => {}), // never resolves
    );

    const { result } = renderHook(() => useAllWorkspaces());

    expect(result.current.isLoading).toBeDefined();
    expect(result.current.error).toBeDefined();
    expect(result.current.refresh).toBeDefined();
  });

  it("returns memberCounts as null initially", () => {
    vi.spyOn(workspaceService, "fetchAllWorkspaces").mockResolvedValue(
      undefined as unknown as WorkspaceListResponse,
    );

    const { result } = renderHook(() => useAllWorkspaces());

    expect(result.current.memberCounts).toBeNull();
  });

  it("fetches member counts after workspaces load", async () => {
    const mockWorkspaces: WorkspaceListItem[] = [
      {
        name: "workspace-1",
        description: "First workspace",
        default_artifact_root: "/artifacts/ws1",
      },
      {
        name: "workspace-2",
        description: "Second workspace",
        default_artifact_root: "/artifacts/ws2",
      },
    ];
    const mockResponse: WorkspaceListResponse = {
      workspaces: mockWorkspaces,
    };
    vi.spyOn(workspaceService, "fetchAllWorkspaces").mockResolvedValue(
      mockResponse,
    );
    vi.spyOn(
      workspaceService,
      "fetchWorkspaceMemberCounts",
    ).mockImplementation(async (name: string) => {
      if (name === "workspace-1") return { users: 5, groups: 2 };
      return { users: 3, groups: 1 };
    });

    const { result } = renderHook(() => useAllWorkspaces());

    await waitFor(() => {
      expect(result.current.memberCounts).not.toBeNull();
    });

    expect(result.current.memberCounts).toEqual({
      "workspace-1": { users: 5, groups: 2 },
      "workspace-2": { users: 3, groups: 1 },
    });
    expect(
      workspaceService.fetchWorkspaceMemberCounts,
    ).toHaveBeenCalledTimes(2);
  });

  it("sets memberCounts to null when allWorkspaces is empty", async () => {
    vi.spyOn(workspaceService, "fetchAllWorkspaces").mockResolvedValue({
      workspaces: [],
    });

    const { result } = renderHook(() => useAllWorkspaces());

    await waitFor(() => {
      expect(result.current.allWorkspaces).toEqual([]);
    });

    expect(result.current.memberCounts).toBeNull();
  });
});
