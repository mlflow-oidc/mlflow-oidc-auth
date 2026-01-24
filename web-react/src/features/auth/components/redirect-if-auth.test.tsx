import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import RedirectIfAuth from "./redirect-if-auth";

const mockUseAuth = vi.fn();

vi.mock("../../../core/hooks/use-auth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("react-router", () => ({
  Navigate: ({ to }: { to: string }) => (
    <div data-testid="navigate" data-to={to} />
  ),
}));

describe("RedirectIfAuth", () => {
  beforeEach(() => {
    mockUseAuth.mockReset();
  });

  it("redirects to default user page when authenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });

    render(
      <RedirectIfAuth>
        <div data-testid="guest">Guest Content</div>
      </RedirectIfAuth>,
    );

    expect(screen.getByTestId("navigate").dataset.to).toBe("/user");
    expect(screen.queryByTestId("guest")).toBeNull();
  });

  it("renders children when not authenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });

    render(
      <RedirectIfAuth to="/custom">
        <div data-testid="guest">Guest Content</div>
      </RedirectIfAuth>,
    );

    expect(screen.getByTestId("guest")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).toBeNull();
  });
});
