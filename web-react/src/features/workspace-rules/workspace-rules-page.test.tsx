import {
  render,
  screen,
  within,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, it, expect, vi, beforeEach } from "vitest";
import WorkspaceRulesPage from "./workspace-rules-page";
import type { WorkspaceRule } from "../../shared/types/entity";
import type { Mock } from "vitest";

vi.mock("react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router")>()),
  Navigate: (props: { to: string }) => (
    <div data-testid="navigate" data-to={props.to} />
  ),
}));

const mockUseRuntimeConfig: Mock<() => { workspaces_enabled: boolean }> =
  vi.fn();
vi.mock("../../shared/context/use-runtime-config", () => ({
  useRuntimeConfig: () => mockUseRuntimeConfig(),
}));

const mockUseUser: Mock<() => { currentUser: { is_admin: boolean } | null }> =
  vi.fn();
vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser(),
}));

const mockRefresh = vi.fn();
const mockUseWorkspaceRules =
  vi.fn<
    typeof import("../../core/hooks/use-workspace-rules").useWorkspaceRules
  >();
vi.mock("../../core/hooks/use-workspace-rules", () => ({
  useWorkspaceRules: () => mockUseWorkspaceRules(),
}));

const mockShowToast = vi.fn();
vi.mock("../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

const mockDeleteWorkspaceRule =
  vi.fn<
    typeof import("../../core/services/workspace-rule-service").deleteWorkspaceRule
  >();
vi.mock("../../core/services/workspace-rule-service", () => ({
  deleteWorkspaceRule: (id: number) => mockDeleteWorkspaceRule(id),
  createWorkspaceRule: vi.fn(),
  updateWorkspaceRule: vi.fn(),
  previewWorkspaceRule: vi.fn(),
  previewUnsavedWorkspaceRule: vi.fn(),
}));

const RULES: WorkspaceRule[] = [
  {
    id: 1,
    name: "tenants",
    pattern: "^team-(?P<ws>[a-z0-9-]+)$",
    permission: "EDIT",
    mode: "enforce",
    enabled: true,
    created_by: "admin@example.com",
    created_at: "2026-09-30T12:00:00+00:00",
    updated_at: "2026-09-30T12:00:00+00:00",
  },
  {
    id: 2,
    name: "partners",
    pattern: "^partner:team-(?P<ws>[a-z]+)$",
    permission: "READ",
    mode: "report",
    enabled: false,
    created_by: "admin@example.com",
    created_at: "2026-09-30T12:00:00+00:00",
    updated_at: "2026-09-30T13:00:00+00:00",
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <WorkspaceRulesPage />
    </MemoryRouter>,
  );
}

describe("WorkspaceRulesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRuntimeConfig.mockReturnValue({ workspaces_enabled: true });
    mockUseUser.mockReturnValue({ currentUser: { is_admin: true } });
    mockUseWorkspaceRules.mockReturnValue({
      rules: RULES,
      allowedPermissions: ["READ", "USE", "EDIT"],
      maxPermission: "EDIT",
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    });
  });

  it("lists name, pattern, permission, mode, enabled and last change", () => {
    renderPage();

    const row = screen
      .getByText("tenants")
      .closest("[role='row']") as HTMLElement;
    expect(
      within(row).getByText("^team-(?P<ws>[a-z0-9-]+)$"),
    ).toBeInTheDocument();
    expect(within(row).getByText("EDIT")).toBeInTheDocument();
    expect(within(row).getByText("Enforce")).toBeInTheDocument();
    expect(within(row).getByText("Yes")).toBeInTheDocument();
    for (const header of [
      "Name",
      "Pattern",
      "Permission",
      "Mode",
      "Enabled",
      "Last change",
    ]) {
      expect(screen.getByText(header)).toBeInTheDocument();
    }
  });

  it("shows the report-mode badge for a report rule", () => {
    renderPage();

    const row = screen
      .getByText("partners")
      .closest("[role='row']") as HTMLElement;
    const badge = within(row).getByText("Report");
    expect(badge).toHaveAttribute(
      "title",
      "Report only: says what it would grant, writes nothing",
    );
    expect(within(row).getByText("No")).toBeInTheDocument();
  });

  it("redirects home when workspaces are disabled", () => {
    mockUseRuntimeConfig.mockReturnValue({ workspaces_enabled: false });

    renderPage();

    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/");
    expect(mockUseWorkspaceRules).not.toHaveBeenCalled();
  });

  it("redirects a non-admin to the forbidden page without fetching rules", () => {
    mockUseUser.mockReturnValue({ currentUser: { is_admin: false } });

    renderPage();

    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/403");
    expect(mockUseWorkspaceRules).not.toHaveBeenCalled();
  });

  it("deletes only after confirmation", async () => {
    mockDeleteWorkspaceRule.mockResolvedValue({
      rule: null,
      changes: [
        {
          action: "remove",
          group: "team-acme",
          workspace: "acme",
          permission: "EDIT",
          reason: null,
          previous: null,
          applied: true,
          rule_id: 1,
        },
      ],
    });
    renderPage();

    fireEvent.click(screen.getByTitle("Delete rule tenants"));
    expect(mockDeleteWorkspaceRule).not.toHaveBeenCalled();
    const dialog = screen
      .getByText("Delete Workspace Rule")
      .closest("dialog") as HTMLElement;
    expect(
      within(dialog).getByText("Grants made by hand stay.", { exact: false }),
    ).toBeInTheDocument();

    fireEvent.click(within(dialog).getByText("Delete Permanently"));

    await waitFor(() =>
      expect(mockDeleteWorkspaceRule).toHaveBeenCalledWith(1),
    );
    await waitFor(() => expect(mockRefresh).toHaveBeenCalled());
    expect(mockShowToast).toHaveBeenCalledWith(
      'Rule "tenants" deleted; 1 workspace permission(s) removed',
      "success",
    );
  });

  it("cancelling the delete confirmation deletes nothing", () => {
    renderPage();

    fireEvent.click(screen.getByTitle("Delete rule tenants"));
    const dialog = screen
      .getByText("Delete Workspace Rule")
      .closest("dialog") as HTMLElement;
    fireEvent.click(within(dialog).getByText("Cancel"));

    expect(mockDeleteWorkspaceRule).not.toHaveBeenCalled();
  });
});
