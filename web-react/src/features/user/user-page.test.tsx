import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { UserPage } from "./user-page";
import * as useCurrentUserModule from "../../core/hooks/use-current-user";
import React from "react";

const mockUseUser = vi.fn();
const mockUseParams = vi.fn(() => ({ tab: "info" }));

vi.mock("react-router", () => ({
  useParams: () => mockUseParams(),
  Link: ({
    children,
    to,
    className,
  }: {
    children: React.ReactNode;
    to: string;
    className?: string;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("../../shared/context/use-runtime-config", () => ({
  useRuntimeConfig: () => ({ gen_ai_gateway_enabled: true }),
}));

vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser() as unknown,
}));

vi.mock("../../core/hooks/use-current-user");

// Mock permission hooks
vi.mock("../../core/hooks/use-user-experiment-permissions", () => ({
  useUserExperimentPermissions: () => ({ permissions: [], isLoading: false }),
}));
vi.mock("../../core/hooks/use-user-model-permissions", () => ({
  useUserRegisteredModelPermissions: () => ({
    permissions: [],
    isLoading: false,
  }),
}));
vi.mock("../../core/hooks/use-user-prompt-permissions", () => ({
  useUserPromptPermissions: () => ({ permissions: [], isLoading: false }),
}));
vi.mock("../../core/hooks/use-user-gateway-endpoint-permissions", () => ({
  useUserGatewayEndpointPermissions: () => ({
    permissions: [],
    isLoading: false,
  }),
}));
vi.mock("../../core/hooks/use-user-gateway-secret-permissions", () => ({
  useUserGatewaySecretPermissions: () => ({
    permissions: [],
    isLoading: false,
  }),
}));
vi.mock("../../core/hooks/use-user-gateway-model-permissions", () => ({
  useUserGatewayModelPermissions: () => ({
    permissions: [],
    isLoading: false,
  }),
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => ({ handleClearSearch: vi.fn(), submittedTerm: "" }),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

vi.mock("../../shared/components/page/page-status", () => ({
  default: ({ isLoading }: { isLoading: boolean }) =>
    isLoading ? <div>Loading...</div> : null,
}));

vi.mock("./components/user-details-card", () => ({
  UserDetailsCard: ({ currentUser }: { currentUser: { username: string } }) => (
    <div>Details for {currentUser.username}</div>
  ),
}));

vi.mock("../tokens/components/user-tokens-panel", () => ({
  UserTokensPanel: ({ username }: { username?: string }) => (
    <div data-testid="tokens-panel">{username ?? "self"}</div>
  ),
}));

describe("UserPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseUser.mockReturnValue({
      currentUser: { username: "testuser" },
      isLoading: false,
      error: null,
    });
    vi.spyOn(useCurrentUserModule, "useCurrentUser").mockReturnValue({
      currentUser: { is_admin: true, username: "admin" },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    } as unknown as ReturnType<typeof useCurrentUserModule.useCurrentUser>);
  });

  it("renders user details when tab is info", () => {
    render(<UserPage />);
    expect(screen.getByText("Details for testuser")).toBeInTheDocument();
  });

  it("renders AI Gateway tabs when enabled", () => {
    render(<UserPage />);
    expect(screen.getByText(/AI\sEndpoints/)).toBeInTheDocument();
    expect(screen.getByText(/AI\sSecrets/)).toBeInTheDocument();
    expect(screen.getByText(/AI\sModels/)).toBeInTheDocument();
  });

  it("links have correct hrefs", () => {
    render(<UserPage />);
    expect(screen.getByText(/AI\sEndpoints/).closest("a")).toHaveAttribute(
      "href",
      "/user/ai-endpoints",
    );
    expect(screen.getByText(/AI\sSecrets/).closest("a")).toHaveAttribute(
      "href",
      "/user/ai-secrets",
    );
  });

  it("has a Tokens tab that shows the signed-in user's own tokens", () => {
    mockUseParams.mockReturnValue({ tab: "tokens" });
    render(<UserPage />);
    expect(screen.getByText("Tokens").closest("a")).toHaveAttribute(
      "href",
      "/user/tokens",
    );
    expect(screen.getByTestId("tokens-panel")).toHaveTextContent("self");
    expect(screen.queryByText("Details for testuser")).not.toBeInTheDocument();
    mockUseParams.mockReturnValue({ tab: "info" });
  });
});
