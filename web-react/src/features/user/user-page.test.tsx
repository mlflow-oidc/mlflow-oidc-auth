import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { UserPage } from "./user-page";
import * as useCurrentUserModule from "../../core/hooks/use-current-user";
import React from "react";

const mockUseUser = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => ({ tab: "info" }),
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

vi.mock("../../shared/components/token-info-block", () => ({
  TokenInfoBlock: () => <div>Token Info</div>,
}));

describe("UserPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseUser.mockReturnValue({
      currentUser: { username: "testuser", password_expiration: 123 },
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
});
