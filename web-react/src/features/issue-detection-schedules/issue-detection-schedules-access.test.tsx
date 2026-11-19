import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Mock } from "vitest";
import App from "../../app";
import { getSidebarData } from "../../shared/components/sidebar-data";

// The real route table and the real ProtectedRoute; only identity and the pages are stubbed.
const mockUseAuth: Mock<() => { isAuthenticated: boolean }> = vi.fn();
const mockUseUser: Mock<
  () => {
    currentUser: { is_admin: boolean } | null;
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
  }
> = vi.fn();

vi.mock("../../core/hooks/use-auth", () => ({
  useAuth: () => mockUseAuth(),
}));
vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser(),
}));
vi.mock("../../core/components/main-layout", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("./issue-detection-schedules-page", () => ({
  default: () => <div>IssueDetectionSchedulesPage</div>,
}));
vi.mock("../forbidden/forbidden-page", () => ({
  default: () => <div>ForbiddenPage</div>,
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

function asUser(isAdmin: boolean) {
  mockUseAuth.mockReturnValue({ isAuthenticated: true });
  mockUseUser.mockReturnValue({
    currentUser: { is_admin: isAdmin },
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  });
}

describe("Issue detection schedules access", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("the route redirects a non-admin to the forbidden page", async () => {
    asUser(false);
    renderAt("/issue-detection-schedules");
    expect(await screen.findByText("ForbiddenPage")).toBeInTheDocument();
    expect(screen.queryByText("IssueDetectionSchedulesPage")).toBeNull();
  });

  it("the route renders the page for an admin", async () => {
    asUser(true);
    renderAt("/issue-detection-schedules");
    expect(
      await screen.findByText("IssueDetectionSchedulesPage"),
    ).toBeInTheDocument();
  });

  it("only an admin sees the nav entry", () => {
    expect(getSidebarData(false, true, true).map((l) => l.label)).not.toContain(
      "Detection schedules",
    );
    const entry = getSidebarData(true, false, false).find(
      (l) => l.label === "Detection schedules",
    );
    expect(entry?.href).toBe("/issue-detection-schedules");
  });
});
