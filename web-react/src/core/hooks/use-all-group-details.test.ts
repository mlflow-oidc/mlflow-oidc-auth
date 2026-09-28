import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useAllGroupDetails } from "./use-all-group-details";
import * as entityService from "../services/entity-service";
import type { GroupDetails } from "../../shared/types/entity";
import * as useAuthModule from "./use-auth";
import type { UseAuthResult } from "./use-auth";
import * as workspaceContext from "../../shared/context/use-workspace";

vi.mock("../services/entity-service");
vi.mock("./use-auth");
vi.mock("../../shared/context/use-workspace");

const mockGroups: GroupDetails[] = [
  { group_name: "data-team", external_id: null, member_count: 3 },
  { group_name: "platform", external_id: "okta-123", member_count: 7 },
];

describe("useAllGroupDetails", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
    vi.spyOn(workspaceContext, "useSelectedWorkspace").mockReturnValue(
      "default",
    );
  });

  it("returns group details", async () => {
    vi.spyOn(entityService, "fetchAllGroupDetails").mockResolvedValue(
      mockGroups,
    );

    const { result } = renderHook(() => useAllGroupDetails());

    await waitFor(() => {
      expect(result.current.groups).toEqual(mockGroups);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("returns an empty array and error on failure", async () => {
    const mockError = new Error("Failed to fetch");
    vi.spyOn(entityService, "fetchAllGroupDetails").mockRejectedValue(
      mockError,
    );

    const { result } = renderHook(() => useAllGroupDetails());

    await waitFor(() => {
      expect(result.current.groups).toEqual([]);
      expect(result.current.error).toEqual(mockError);
    });
  });
});
