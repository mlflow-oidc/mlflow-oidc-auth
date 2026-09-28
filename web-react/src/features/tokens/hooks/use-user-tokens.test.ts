import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useUserTokens } from "./use-user-tokens";
import * as service from "../services/user-token-service";
import * as useAuthModule from "../../../core/hooks/use-auth";
import type { UseAuthResult } from "../../../core/hooks/use-auth";
import * as workspaceContext from "../../../shared/context/use-workspace";
import type { UserToken } from "../../../shared/types/user";

vi.mock("../services/user-token-service");
vi.mock("../../../core/hooks/use-auth");
vi.mock("../../../shared/context/use-workspace");

const token: UserToken = {
  id: 1,
  name: "ci",
  token_prefix: "mlf_ab12cd34",
  created_at: "2026-09-01T00:00:00Z",
  created_by: "alice",
  expires_at: "2027-01-01T23:59:59Z",
  last_used_at: null,
  active: true,
};

describe("useUserTokens", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
    vi.spyOn(workspaceContext, "useSelectedWorkspace").mockReturnValue(null);
  });

  it("loads the owner's tokens", async () => {
    vi.mocked(service.listUserTokens).mockResolvedValue([token]);
    const { result } = renderHook(() => useUserTokens("bob"));
    await waitFor(() => expect(result.current.tokens).toEqual([token]));
    expect(service.listUserTokens).toHaveBeenCalledWith(
      "bob",
      expect.any(AbortSignal),
    );
  });

  it("returns an empty list and the error on failure", async () => {
    const error = new Error("boom");
    vi.mocked(service.listUserTokens).mockRejectedValue(error);
    const { result } = renderHook(() => useUserTokens(undefined));
    await waitFor(() => expect(result.current.error).toEqual(error));
    expect(result.current.tokens).toEqual([]);
  });
});
