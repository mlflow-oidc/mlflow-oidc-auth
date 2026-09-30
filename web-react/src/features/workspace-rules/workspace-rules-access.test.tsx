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
vi.mock("./workspace-rules-page", () => ({
  default: () => <div>WorkspaceRulesPage</div>,
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

describe("Workspace rules access", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("the route redirects a non-admin to the forbidden page", async () => {
    asUser(false);

    renderAt("/workspace-rules");

    expect(await screen.findByText("ForbiddenPage")).toBeInTheDocument();
    expect(screen.queryByText("WorkspaceRulesPage")).toBeNull();
  });

  it("the route renders the page for an admin", async () => {
    asUser(true);

    renderAt("/workspace-rules");

    expect(await screen.findByText("WorkspaceRulesPage")).toBeInTheDocument();
  });

  it("a non-admin sees no nav entry, even with workspaces enabled", () => {
    const labels = getSidebarData(false, true, true).map((l) => l.label);
    expect(labels).not.toContain("Workspace rules");
  });

  it("the nav entry is hidden when workspaces are disabled", () => {
    const labels = getSidebarData(true, true, false).map((l) => l.label);
    expect(labels).not.toContain("Workspace rules");
  });

  it("an admin sees the nav entry when workspaces are enabled", () => {
    const entry = getSidebarData(true, false, true).find(
      (l) => l.label === "Workspace rules",
    );
    expect(entry?.href).toBe("/workspace-rules");
  });
});
