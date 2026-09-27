import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import * as useAuthModule from "./use-auth";
import * as workspaceService from "../services/workspace-service";
import { useAllWorkspaces } from "./use-all-workspaces";
import type {
  WorkspaceListItem,
  WorkspaceListResponse,
  WorkspaceMemberCounts,
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
    ).mockImplementation((name: string) => {
      if (name === "workspace-1")
        return Promise.resolve({ users: 5, groups: 2 });
      return Promise.resolve({ users: 3, groups: 1 });
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

  it("keeps memberCounts null after empty -> non-empty with a reused name, until the refetch resolves", async () => {
    const ws: WorkspaceListItem = {
      name: "workspace-1",
      description: "First workspace",
      default_artifact_root: "/artifacts/ws1",
    };

    let resolveInitial: (counts: WorkspaceMemberCounts) => void = () =>
      undefined;
    let resolveAfterReturn: (counts: WorkspaceMemberCounts) => void = () =>
      undefined;

    vi.spyOn(workspaceService, "fetchAllWorkspaces")
      .mockResolvedValueOnce({ workspaces: [ws] })
      .mockResolvedValueOnce({ workspaces: [] })
      .mockResolvedValueOnce({ workspaces: [{ ...ws }] });

    vi.spyOn(workspaceService, "fetchWorkspaceMemberCounts")
      .mockImplementationOnce(
        () =>
          new Promise<WorkspaceMemberCounts>((resolve) => {
            resolveInitial = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<WorkspaceMemberCounts>((resolve) => {
            resolveAfterReturn = resolve;
          }),
      );

    const { result } = renderHook(() => useAllWorkspaces());

    await waitFor(() => {
      expect(result.current.allWorkspaces).toEqual([ws]);
    });
    expect(result.current.memberCounts).toBeNull();

    await act(async () => {
      resolveInitial({ users: 5, groups: 2 });
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(result.current.memberCounts).toEqual({
        "workspace-1": { users: 5, groups: 2 },
      });
    });

    // The list empties out...
    act(() => result.current.refresh());
    await waitFor(() => {
      expect(result.current.allWorkspaces).toEqual([]);
    });
    expect(result.current.memberCounts).toBeNull();

    // ...and the same workspace name comes back. The stale counts fetched
    // for the earlier (now different-reference) list must not reappear
    // while the new fetch is still in flight.
    act(() => result.current.refresh());
    await waitFor(() => {
      expect(result.current.allWorkspaces).toEqual([ws]);
    });
    expect(result.current.memberCounts).toBeNull();

    await act(async () => {
      resolveAfterReturn({ users: 1, groups: 1 });
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(result.current.memberCounts).toEqual({
        "workspace-1": { users: 1, groups: 1 },
      });
    });
  });

  it("ignores an out-of-order fetch result from a superseded workspace list", async () => {
    const wsA: WorkspaceListItem = {
      name: "workspace-a",
      description: "A",
      default_artifact_root: "/artifacts/a",
    };
    const wsB: WorkspaceListItem = {
      name: "workspace-b",
      description: "B",
      default_artifact_root: "/artifacts/b",
    };

    let resolveStale: (counts: WorkspaceMemberCounts) => void = () =>
      undefined;
    let resolveFresh: (counts: WorkspaceMemberCounts) => void = () =>
      undefined;

    vi.spyOn(workspaceService, "fetchAllWorkspaces")
      .mockResolvedValueOnce({ workspaces: [wsA] })
      .mockResolvedValueOnce({ workspaces: [wsB] });

    vi.spyOn(workspaceService, "fetchWorkspaceMemberCounts")
      .mockImplementationOnce(
        () =>
          new Promise<WorkspaceMemberCounts>((resolve) => {
            resolveStale = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<WorkspaceMemberCounts>((resolve) => {
            resolveFresh = resolve;
          }),
      );

    const { result } = renderHook(() => useAllWorkspaces());

    await waitFor(() => {
      expect(result.current.allWorkspaces).toEqual([wsA]);
    });
    expect(result.current.memberCounts).toBeNull();

    // Move on to workspace B before A's member-count fetch resolves.
    act(() => result.current.refresh());
    await waitFor(() => {
      expect(result.current.allWorkspaces).toEqual([wsB]);
    });
    expect(result.current.memberCounts).toBeNull();

    // B's fetch resolves first.
    await act(async () => {
      resolveFresh({ users: 9, groups: 4 });
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(result.current.memberCounts).toEqual({
        "workspace-b": { users: 9, groups: 4 },
      });
    });

    // A's stale fetch resolves after B's — it must not overwrite B's counts.
    await act(async () => {
      resolveStale({ users: 1, groups: 1 });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(result.current.memberCounts).toEqual({
      "workspace-b": { users: 9, groups: 4 },
    });
  });
});
