import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ScimPage from "./scim-page";
import * as useScimTokensModule from "./hooks/use-scim-tokens";
import * as useToastModule from "../../shared/components/toast/use-toast";
import * as scimTokenService from "./services/scim-token-service";
import * as useScimStatusModule from "./hooks/use-scim-status";
import * as useScimActivityModule from "./hooks/use-scim-activity";
import type { ScimToken, ScimTokenWithSecret } from "../../shared/types/scim";

vi.mock("./hooks/use-scim-tokens");
vi.mock("../../shared/components/toast/use-toast");
vi.mock("./services/scim-token-service");
vi.mock("./hooks/use-scim-status");
vi.mock("./hooks/use-scim-activity");

vi.mock("../../shared/context/use-runtime-config", () => ({
  useRuntimeConfig: () => ({
    basePath: "/base",
    uiPath: "/ui",
    provider: "oidc",
    authenticated: true,
    gen_ai_gateway_enabled: false,
    workspaces_enabled: false,
  }),
}));

describe("ScimPage", () => {
  const activeToken: ScimToken = {
    id: 1,
    name: "Entra ID",
    token_prefix: "scim_abcd",
    created_at: "2026-01-01T00:00:00Z",
    created_by: "admin",
    last_used_at: "2026-02-01T00:00:00Z",
    expires_at: null,
    revoked_at: null,
  };

  const revokedToken: ScimToken = {
    id: 2,
    name: "Okta",
    token_prefix: "scim_wxyz",
    created_at: "2026-01-01T00:00:00Z",
    created_by: "admin",
    last_used_at: null,
    expires_at: null,
    revoked_at: "2026-03-01T00:00:00Z",
  };

  const expiredToken: ScimToken = {
    id: 3,
    name: "Legacy",
    token_prefix: "scim_lgcy",
    created_at: "2026-01-01T00:00:00Z",
    created_by: "admin",
    last_used_at: null,
    expires_at: "2020-01-01T00:00:00Z",
    revoked_at: null,
  };

  const mockShowToast = vi.fn();
  const mockRefresh = vi.fn();
  const mockRefreshStatus = vi.fn();
  const mockRefreshActivity = vi.fn();
  const mockLoadMore = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useScimTokensModule, "useScimTokens").mockReturnValue({
      tokens: [activeToken, revokedToken],
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    });

    vi.spyOn(useScimStatusModule, "useScimStatus").mockReturnValue({
      status: {
        provisioning_healthy: false,
        last_success_at: "2026-02-01T00:00:00Z",
        last_error_at: "2026-02-02T00:00:00Z",
        last_error: "uniqueness: already exists",
        requests_24h: 4,
        errors_24h: 1,
        auth_failures_24h: 0,
        last_auth_failure_at: null,
        healthy_window_seconds: 86400,
        retention_days: 30,
        tokens: [],
      },
      isLoading: false,
      error: null,
      refresh: mockRefreshStatus,
    });
    vi.spyOn(useScimActivityModule, "useScimActivity").mockReturnValue({
      entries: [
        {
          id: 1,
          at: "2026-02-02T00:00:00Z",
          token_id: 1,
          token_name: "entra-activity",
          method: "POST",
          path: "/Users",
          resource_id: null,
          status: 409,
          outcome: "client_error",
          error: "uniqueness: already exists",
          duration_ms: 3,
        },
      ],
      hasMore: true,
      isLoading: false,
      isLoadingMore: false,
      error: null,
      loadMore: mockLoadMore,
      refresh: mockRefreshActivity,
    });

    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as unknown as ReturnType<typeof useToastModule.useToast>);
  });

  it("renders the provisioning endpoint and the tokens table", () => {
    render(<ScimPage />);
    expect(screen.getByText("Provisioning endpoint")).toBeInTheDocument();
    expect(
      screen.getByText(`${window.location.origin}/base/scim/v2`),
    ).toBeInTheDocument();
    expect(screen.getByText("Entra ID")).toBeInTheDocument();
    expect(screen.getByText("Okta")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Revoked")).toBeInTheDocument();
  });

  it("creates a token and shows the plaintext exactly once", async () => {
    const created: ScimTokenWithSecret = {
      ...activeToken,
      id: 3,
      name: "New Token",
      token: "scim_plaintext_value",
    };
    vi.spyOn(scimTokenService, "createScimToken").mockResolvedValue(created);

    render(<ScimPage />);
    fireEvent.click(screen.getByText("Create token"));

    const nameInput = screen.getByLabelText(/Name\*/i);
    fireEvent.change(nameInput, { target: { value: "New Token" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(scimTokenService.createScimToken).toHaveBeenCalledWith(
        expect.objectContaining({ name: "New Token" }),
      );
    });

    expect(
      await screen.findByDisplayValue("scim_plaintext_value"),
    ).toBeInTheDocument();
    expect(mockRefresh).toHaveBeenCalled();

    // The plaintext appears exactly once on the page.
    expect(
      screen.getAllByDisplayValue("scim_plaintext_value"),
    ).toHaveLength(1);
  });

  it("rotates a token after confirmation and refreshes the list", async () => {
    const rotated: ScimTokenWithSecret = {
      ...activeToken,
      token: "scim_rotated_value",
    };
    vi.spyOn(scimTokenService, "rotateScimToken").mockResolvedValue(rotated);

    render(<ScimPage />);
    const rotateButtons = screen.getAllByTitle("Rotate");
    fireEvent.click(rotateButtons[0]);

    expect(screen.getByText("Rotate SCIM token")).toBeInTheDocument();
    expect(screen.getByText(/overlap window/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Rotate token" }));

    await waitFor(() => {
      expect(scimTokenService.rotateScimToken).toHaveBeenCalledWith(
        activeToken.id,
      );
      expect(mockRefresh).toHaveBeenCalled();
    });

    expect(
      await screen.findByDisplayValue("scim_rotated_value"),
    ).toBeInTheDocument();
  });

  it("revokes a token after confirmation", async () => {
    vi.spyOn(scimTokenService, "revokeScimToken").mockResolvedValue({
      ...activeToken,
      revoked_at: "2026-04-01T00:00:00Z",
    });

    render(<ScimPage />);
    const revokeButtons = screen.getAllByTitle("Revoke");
    fireEvent.click(revokeButtons[0]);

    expect(screen.getByText("Revoke SCIM token")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Revoke token" }));

    await waitFor(() => {
      expect(scimTokenService.revokeScimToken).toHaveBeenCalledWith(
        activeToken.id,
      );
      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  it("disables Rotate and Revoke actions for an already-revoked token", () => {
    render(<ScimPage />);
    const rotateButtons = screen.getAllByTitle("Rotate");
    const revokeButtons = screen.getAllByTitle("Revoke");

    // Second row corresponds to the revoked token.
    expect(rotateButtons[1]).toBeDisabled();
    expect(revokeButtons[1]).toBeDisabled();
  });

  it("shows Expired (not Expiring) for a token whose expiry is in the past, and disables its actions", () => {
    vi.spyOn(useScimTokensModule, "useScimTokens").mockReturnValue({
      tokens: [activeToken, expiredToken],
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    });

    render(<ScimPage />);

    expect(screen.getByText("Expired")).toBeInTheDocument();
    expect(screen.queryByText("Expiring")).not.toBeInTheDocument();

    const rotateButtons = screen.getAllByTitle("Rotate");
    const revokeButtons = screen.getAllByTitle("Revoke");
    // Second row corresponds to the expired token.
    expect(rotateButtons[1]).toBeDisabled();
    expect(revokeButtons[1]).toBeDisabled();
  });

  it("shows provisioning status and recent activity with its controls", () => {
    render(<ScimPage />);
    expect(screen.getByTestId("scim-health")).toHaveTextContent("Unhealthy");
    expect(screen.getByTestId("scim-last-error")).toHaveTextContent(
      "uniqueness: already exists",
    );
    expect(screen.getByTestId("scim-activity-1")).toHaveAttribute(
      "data-error",
      "true",
    );

    fireEvent.change(screen.getByLabelText("Filter by outcome"), {
      target: { value: "client_error" },
    });
    expect(useScimActivityModule.useScimActivity).toHaveBeenLastCalledWith(
      "client_error",
    );

    fireEvent.click(screen.getByText("Load more"));
    expect(mockLoadMore).toHaveBeenCalled();
    fireEvent.click(screen.getByText("Refresh"));
    expect(mockRefreshActivity).toHaveBeenCalled();
    expect(mockRefreshStatus).toHaveBeenCalled();
  });

  it("keeps the secret modal mounted and visible if the post-create refresh fails (#1)", async () => {
    let hookState: ReturnType<typeof useScimTokensModule.useScimTokens> = {
      tokens: [activeToken],
      isLoading: false,
      error: null,
      refresh: () => {
        // Simulate the refetch that `refresh()` kicks off flipping into a loading state
        // immediately, the way the real `useApi`-backed hook does.
        hookState = { ...hookState, isLoading: true };
      },
    };
    vi.spyOn(useScimTokensModule, "useScimTokens").mockImplementation(
      () => hookState,
    );

    const created: ScimTokenWithSecret = {
      ...activeToken,
      id: 9,
      name: "New Token",
      token: "scim_plaintext_xyz",
    };
    vi.spyOn(scimTokenService, "createScimToken").mockResolvedValue(created);

    const { rerender } = render(<ScimPage />);
    fireEvent.click(screen.getByText("Create token"));
    fireEvent.change(screen.getByLabelText(/Name\*/i), {
      target: { value: "New Token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(
      await screen.findByDisplayValue("scim_plaintext_xyz"),
    ).toBeInTheDocument();

    // The refetch triggered by handleCreated is now "in flight" (isLoading: true). The secret
    // modal must still be visible even though the rest of the page is gated on !isLoading.
    expect(screen.getByDisplayValue("scim_plaintext_xyz")).toBeInTheDocument();

    // Now simulate that refetch failing outright.
    hookState = { ...hookState, isLoading: false, error: new Error("boom") };
    rerender(<ScimPage />);

    expect(screen.getByDisplayValue("scim_plaintext_xyz")).toBeInTheDocument();
  });
});
