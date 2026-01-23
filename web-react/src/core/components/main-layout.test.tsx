import { render, screen, fireEvent } from "@testing-library/react";
import { vi } from "vitest";
import MainLayout from "./main-layout";

const mockUseUser = vi.fn();

vi.mock("../hooks/use-user", () => ({
  useUser: () => mockUseUser(),
}));

vi.mock("../../shared/components/header", () => ({
  __esModule: true,
  default: ({ userName = "User" }: { userName?: string }) => (
    <div data-testid="header">header-{userName}</div>
  ),
}));

vi.mock("../../shared/components/sidebar", () => ({
  __esModule: true,
  default: ({
    isOpen,
    widthClass,
    toggleSidebar,
  }: {
    isOpen: boolean;
    widthClass: string;
    toggleSidebar: () => void;
  }) => (
    <div data-testid="sidebar">
      <span data-testid="sidebar-open">{String(isOpen)}</span>
      <span data-testid="sidebar-width">{widthClass}</span>
      <button
        type="button"
        data-testid="sidebar-toggle"
        onClick={toggleSidebar}
      >
        toggle
      </button>
    </div>
  ),
}));

describe("MainLayout", () => {
  beforeEach(() => {
    mockUseUser.mockReset();
  });

  it("renders header, sidebar and children with display name", () => {
    mockUseUser.mockReturnValue({
      currentUser: {
        display_name: "Jane Doe",
        username: "jane",
        is_admin: false,
      },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(
      <MainLayout>
        <div data-testid="content">Child Content</div>
      </MainLayout>
    );

    expect(screen.getByTestId("header").textContent).toContain("Jane Doe");
    expect(screen.getByTestId("content")).toBeInTheDocument();
    expect(screen.getByTestId("sidebar-open").textContent).toBe("true");
    expect(screen.getByTestId("sidebar-width").textContent).toContain(
      "w-[200px]"
    );

    fireEvent.click(screen.getByTestId("sidebar-toggle"));

    expect(screen.getByTestId("sidebar-open").textContent).toBe("false");
    expect(screen.getByTestId("sidebar-width").textContent).toBe("w-10");
  });

  it("falls back to username when display name missing", () => {
    mockUseUser.mockReturnValue({
      currentUser: {
        username: "fallback-user",
        is_admin: false,
      },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(
      <MainLayout>
        <div>Content</div>
      </MainLayout>
    );

    expect(screen.getByTestId("header").textContent).toContain(
      "fallback-user"
    );
  });

  it("uses Guest label when no user present", () => {
    mockUseUser.mockReturnValue({
      currentUser: null,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(
      <MainLayout>
        <div>Content</div>
      </MainLayout>
    );

    expect(screen.getByTestId("header").textContent).toContain("Guest");
  });
});
