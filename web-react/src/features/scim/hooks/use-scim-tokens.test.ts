import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useScimTokens } from "./use-scim-tokens";
import * as scimTokenService from "../services/scim-token-service";
import type { ScimToken } from "../../../shared/types/scim";
import * as useAuthModule from "../../../core/hooks/use-auth";
import type { UseAuthResult } from "../../../core/hooks/use-auth";
import * as workspaceContext from "../../../shared/context/use-workspace";

vi.mock("../services/scim-token-service");
vi.mock("../../../core/hooks/use-auth");
vi.mock("../../../shared/context/use-workspace");

describe("useScimTokens", () => {
  const mockToken: ScimToken = {
    id: 1,
    name: "Entra ID",
    token_prefix: "scim_abcd",
    created_at: "2026-01-01T00:00:00Z",
    created_by: "admin",
    last_used_at: null,
    expires_at: null,
    revoked_at: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
    vi.spyOn(workspaceContext, "useSelectedWorkspace").mockReturnValue(
      "default",
    );
  });

  it("returns SCIM tokens", async () => {
    vi.spyOn(scimTokenService, "listScimTokens").mockResolvedValue([
      mockToken,
    ]);

    const { result } = renderHook(() => useScimTokens());

    await waitFor(() => {
      expect(result.current.tokens).toEqual([mockToken]);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("returns empty array and error on failure", async () => {
    const mockError = new Error("Failed to fetch");
    vi.spyOn(scimTokenService, "listScimTokens").mockRejectedValue(mockError);

    const { result } = renderHook(() => useScimTokens());

    await waitFor(() => {
      expect(result.current.tokens).toEqual([]);
      expect(result.current.error).toEqual(mockError);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("refresh triggers a refetch", async () => {
    const listSpy = vi
      .spyOn(scimTokenService, "listScimTokens")
      .mockResolvedValue([mockToken]);

    const { result } = renderHook(() => useScimTokens());

    await waitFor(() => {
      expect(result.current.tokens).toHaveLength(1);
    });

    const callCountAfterFirstFetch = listSpy.mock.calls.length;

    result.current.refresh();

    await waitFor(() => {
      expect(listSpy.mock.calls.length).toBeGreaterThan(
        callCountAfterFirstFetch,
      );
    });
  });
});
