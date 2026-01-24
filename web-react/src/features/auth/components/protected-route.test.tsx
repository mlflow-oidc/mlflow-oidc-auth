import React from "react";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import ProtectedRoute from "./protected-route";

const mockUseAuth = vi.fn();
const mockUseUser = vi.fn();

vi.mock("../../../core/hooks/use-auth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("../../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser(),
}));

vi.mock("react-router", () => ({
  Navigate: ({ to }: { to: string }) => (
    <div data-testid="navigate" data-to={to} />
  ),
}));

vi.mock("../../../shared/components/loading-spinner", () => ({
  LoadingSpinner: () => <div data-testid="spinner" />,
}));

vi.mock("../../../shared/components/button", () => ({
  Button: ({
    children,
    ...rest
  }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button type="button" {...rest}>
      {children}
    </button>
  ),
}));

describe("ProtectedRoute", () => {
  beforeEach(() => {
    mockUseAuth.mockReset();
    mockUseUser.mockReset();
  });

  it("redirects to auth when unauthenticated", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false });
    mockUseUser.mockReturnValue({
      currentUser: null,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(screen.getByTestId("navigate").dataset.to).toBe("/auth");
  });

  it("shows error state when user fetch fails", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockUseUser.mockReturnValue({
      currentUser: null,
      isLoading: false,
      error: new Error("Failed to load user"),
      refresh: vi.fn(),
    });

    render(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(screen.getByText("Error Loading User")).toBeInTheDocument();
    expect(screen.getByText("Failed to load user")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).toBeNull();
  });

  it("renders loading spinner while user is loading", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockUseUser.mockReturnValue({
      currentUser: null,
      isLoading: true,
      error: null,
      refresh: vi.fn(),
    });

    render(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(screen.getByTestId("spinner")).toBeInTheDocument();
  });

  it("renders loading spinner when user missing after load", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockUseUser.mockReturnValue({
      currentUser: null,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(
      <ProtectedRoute>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(screen.getByTestId("spinner")).toBeInTheDocument();
  });

  it("redirects non-admins when admin is required", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockUseUser.mockReturnValue({
      currentUser: {
        username: "user",
        is_admin: false,
      },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(
      <ProtectedRoute isAdminRequired>
        <div>Secret</div>
      </ProtectedRoute>,
    );

    expect(screen.getByTestId("navigate").dataset.to).toBe("/403");
  });

  it("renders children when authenticated and authorized", () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true });
    mockUseUser.mockReturnValue({
      currentUser: {
        username: "admin",
        is_admin: true,
      },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(
      <ProtectedRoute>
        <div data-testid="secret">Secret</div>
      </ProtectedRoute>,
    );

    expect(screen.getByTestId("secret")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).toBeNull();
  });
});
