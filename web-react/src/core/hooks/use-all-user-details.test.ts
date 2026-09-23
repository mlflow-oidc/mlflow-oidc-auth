import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useAllUserDetails } from "./use-all-user-details";
import * as userService from "../services/user-service";
import type { UserDetails } from "../../shared/types/user";
import * as useAuthModule from "./use-auth";
import type { UseAuthResult } from "./use-auth";
import * as workspaceContext from "../../shared/context/use-workspace";

vi.mock("../services/user-service");
vi.mock("./use-auth");
vi.mock("../../shared/context/use-workspace");

const mockUsers: UserDetails[] = [
  {
    username: "alice@example.com",
    display_name: "Alice",
    is_admin: false,
    is_service_account: false,
    active: true,
    managed_by: "manual",
  },
  {
    username: "bob@example.com",
    display_name: "Bob",
    is_admin: true,
    is_service_account: false,
    active: false,
    managed_by: "scim",
  },
];

describe("useAllUserDetails", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
    vi.spyOn(workspaceContext, "useSelectedWorkspace").mockReturnValue(
      "default",
    );
  });

  it("returns user details from fetchAllUserDetails", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockUsers);
    vi.spyOn(userService, "fetchAllUserDetails").mockReturnValue(fetcher);

    const { result } = renderHook(() => useAllUserDetails());

    await waitFor(() => {
      expect(result.current.users).toEqual(mockUsers);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("passes the service flag through to fetchAllUserDetails", () => {
    const fetcherSpy = vi.spyOn(userService, "fetchAllUserDetails");
    fetcherSpy.mockReturnValue(vi.fn().mockResolvedValue([]));

    renderHook(() => useAllUserDetails(false));

    expect(fetcherSpy).toHaveBeenCalledWith(false);
  });

  it("returns an error on failure", async () => {
    const mockError = new Error("Failed to fetch");
    vi.spyOn(userService, "fetchAllUserDetails").mockReturnValue(
      vi.fn().mockRejectedValue(mockError),
    );

    const { result } = renderHook(() => useAllUserDetails());

    await waitFor(() => {
      expect(result.current.users).toEqual([]);
      expect(result.current.error).toEqual(mockError);
    });
  });

  it("applies local overrides from updateLocalUser", async () => {
    vi.spyOn(userService, "fetchAllUserDetails").mockReturnValue(
      vi.fn().mockResolvedValue(mockUsers),
    );

    const { result } = renderHook(() => useAllUserDetails());

    await waitFor(() => {
      expect(result.current.users).toHaveLength(2);
    });

    act(() => {
      result.current.updateLocalUser("alice@example.com", { active: false });
    });

    expect(
      result.current.users.find((u) => u.username === "alice@example.com")
        ?.active,
    ).toBe(false);
    // Untouched fields are preserved.
    expect(
      result.current.users.find((u) => u.username === "alice@example.com")
        ?.display_name,
    ).toBe("Alice");
  });

  it("clears local overrides and refetches on refresh", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockUsers);
    vi.spyOn(userService, "fetchAllUserDetails").mockReturnValue(fetcher);

    const { result } = renderHook(() => useAllUserDetails());

    await waitFor(() => {
      expect(result.current.users).toHaveLength(2);
    });

    act(() => {
      result.current.updateLocalUser("alice@example.com", { active: false });
    });

    expect(
      result.current.users.find((u) => u.username === "alice@example.com")
        ?.active,
    ).toBe(false);

    act(() => {
      result.current.refresh();
    });

    await waitFor(() => {
      expect(
        result.current.users.find((u) => u.username === "alice@example.com")
          ?.active,
      ).toBe(true);
    });
  });
});
