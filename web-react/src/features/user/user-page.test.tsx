import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { UserPage } from "./user-page";

const mockUseUser = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => ({ tab: "info" }),
  Link: ({ children, to, className }: any) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser(),
}));

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
  default: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("../../shared/components/page/page-status", () => ({
  default: ({ isLoading }: any) => (isLoading ? <div>Loading...</div> : null),
}));

vi.mock("./components/user-details-card", () => ({
  UserDetailsCard: ({ currentUser }: any) => (
    <div>Details for {currentUser.username}</div>
  ),
}));

vi.mock("../../shared/components/token-info-block", () => ({
  TokenInfoBlock: () => <div>Token Info</div>,
}));

describe("UserPage", () => {
  beforeEach(() => {
    mockUseUser.mockReturnValue({
      currentUser: { username: "testuser", password_expiration: 123 },
      isLoading: false,
      error: null,
    });
  });

  it("renders user details when tab is info", () => {
    render(<UserPage />);
    expect(screen.getByText("Details for testuser")).toBeInTheDocument();
  });
});
