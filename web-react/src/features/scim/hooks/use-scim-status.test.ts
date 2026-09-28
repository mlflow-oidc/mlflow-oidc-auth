import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useScimStatus } from "./use-scim-status";
import * as service from "../services/scim-activity-service";
import * as useAuthModule from "../../../core/hooks/use-auth";
import type { UseAuthResult } from "../../../core/hooks/use-auth";
import * as workspaceContext from "../../../shared/context/use-workspace";
import type { ScimProvisioningStatus } from "../../../shared/types/scim";

vi.mock("../services/scim-activity-service");
vi.mock("../../../core/hooks/use-auth");
vi.mock("../../../shared/context/use-workspace");

const status: ScimProvisioningStatus = {
  provisioning_healthy: true,
  last_success_at: "2026-09-01T00:00:00+00:00",
  last_error_at: null,
  last_error: null,
  requests_24h: 3,
  errors_24h: 0,
  auth_failures_24h: 0,
  last_auth_failure_at: null,
  healthy_window_seconds: 86400,
  retention_days: 30,
  tokens: [],
};

describe("useScimStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
    vi.spyOn(workspaceContext, "useSelectedWorkspace").mockReturnValue(
      "default",
    );
  });

  it("returns the status", async () => {
    vi.spyOn(service, "fetchScimStatus").mockResolvedValue(status);
    const { result } = renderHook(() => useScimStatus());
    await waitFor(() => {
      expect(result.current.status).toEqual(status);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("returns the error on failure", async () => {
    const error = new Error("boom");
    vi.spyOn(service, "fetchScimStatus").mockRejectedValue(error);
    const { result } = renderHook(() => useScimStatus());
    await waitFor(() => {
      expect(result.current.error).toEqual(error);
      expect(result.current.status).toBeNull();
    });
  });
});
