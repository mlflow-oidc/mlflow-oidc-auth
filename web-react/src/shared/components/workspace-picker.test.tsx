import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, type Mock } from "vitest";
import { MemoryRouter } from "react-router";
import { WorkspacePicker } from "./workspace-picker";

// Mock dependencies
vi.mock("../context/use-workspace", () => ({
  useWorkspace: vi.fn(),
}));

vi.mock("../../core/hooks/use-all-workspaces", () => ({
  useAllWorkspaces: vi.fn(),
}));

vi.mock("../context/use-runtime-config", () => ({
  useRuntimeConfig: vi.fn(),
}));

import { useWorkspace } from "../context/use-workspace";
import { useAllWorkspaces } from "../../core/hooks/use-all-workspaces";
import { useRuntimeConfig } from "../context/use-runtime-config";

const mockSetSelectedWorkspace = vi.fn();

const defaultWorkspaceContext = {
  selectedWorkspace: null,
  setSelectedWorkspace: mockSetSelectedWorkspace,
};

const defaultAllWorkspaces = {
  allWorkspaces: [
    { name: "workspace-a", description: "First", default_artifact_root: "/" },
    { name: "workspace-b", description: "Second", default_artifact_root: "/" },
    {
      name: "production",
      description: "Production",
      default_artifact_root: "/",
    },
  ],
  isLoading: false,
  error: null,
  refresh: vi.fn(),
};

const enabledConfig = {
  basePath: "/",
  uiPath: "/ui",
  provider: "oidc",
  authenticated: true,
  gen_ai_gateway_enabled: false,
  workspaces_enabled: true,
};

const disabledConfig = {
  ...enabledConfig,
  workspaces_enabled: false,
};

describe("WorkspacePicker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useWorkspace as Mock).mockReturnValue(defaultWorkspaceContext);
    (useAllWorkspaces as Mock).mockReturnValue(defaultAllWorkspaces);
    (useRuntimeConfig as Mock).mockReturnValue(enabledConfig);
  });

  it("renders nothing when workspaces_enabled is false", () => {
    (useRuntimeConfig as Mock).mockReturnValue(disabledConfig);
    const { container } = render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders workspace picker button when workspaces_enabled is true", () => {
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("Select workspace")).toBeInTheDocument();
  });

  it("shows 'All Workspaces' when no workspace selected", () => {
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    expect(screen.getByText("All Workspaces")).toBeInTheDocument();
  });

  it("shows selected workspace name in button", () => {
    (useWorkspace as Mock).mockReturnValue({
      ...defaultWorkspaceContext,
      selectedWorkspace: "workspace-a",
    });
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    expect(screen.getByText("workspace-a")).toBeInTheDocument();
  });

  it("opens dropdown on click and shows workspace list", () => {
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    const button = screen.getByLabelText("Select workspace");
    fireEvent.click(button);

    expect(screen.getByPlaceholderText("Filter workspaces...")).toBeInTheDocument();
    expect(screen.getByText("workspace-a")).toBeInTheDocument();
    expect(screen.getByText("workspace-b")).toBeInTheDocument();
    expect(screen.getByText("production")).toBeInTheDocument();
  });

  it("filters workspaces by search input", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByLabelText("Select workspace"));

    const searchInput = screen.getByPlaceholderText("Filter workspaces...");
    await user.type(searchInput, "prod");

    expect(screen.getByText("production")).toBeInTheDocument();
    expect(screen.queryByText("workspace-a")).not.toBeInTheDocument();
    expect(screen.queryByText("workspace-b")).not.toBeInTheDocument();
  });

  it("selecting a workspace calls setSelectedWorkspace and closes dropdown", () => {
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByLabelText("Select workspace"));

    // Click on a workspace
    fireEvent.click(screen.getByText("workspace-a"));

    expect(mockSetSelectedWorkspace).toHaveBeenCalledWith("workspace-a");
    // Dropdown should close - no listbox visible
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("selecting 'All Workspaces' calls setSelectedWorkspace(null)", () => {
    (useWorkspace as Mock).mockReturnValue({
      ...defaultWorkspaceContext,
      selectedWorkspace: "workspace-a",
    });
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByLabelText("Select workspace"));

    // The "All Workspaces" option in the dropdown (not in the button)
    const allWorkspacesOptions = screen.getAllByText(/All Workspaces/);
    // Click the one in the dropdown (role=option)
    const dropdownOption = allWorkspacesOptions.find((el) => el.getAttribute("role") === "option");
    fireEvent.click(dropdownOption!);

    expect(mockSetSelectedWorkspace).toHaveBeenCalledWith(null);
  });

  it("closes dropdown on Escape key", () => {
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByLabelText("Select workspace"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("toggles dropdown on Ctrl+K", () => {
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    // Open with Ctrl+K
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    // Close with Ctrl+K
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes dropdown on click outside", () => {
    render(
      <MemoryRouter>
        <div>
          <div data-testid="outside">Outside</div>
          <WorkspacePicker />
        </div>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByLabelText("Select workspace"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("shows checkmark on selected workspace", () => {
    (useWorkspace as Mock).mockReturnValue({
      ...defaultWorkspaceContext,
      selectedWorkspace: "workspace-b",
    });
    render(
      <MemoryRouter>
        <WorkspacePicker />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByLabelText("Select workspace"));

    const options = screen.getAllByRole("option");
    const selectedOption = options.find((el) => el.getAttribute("aria-selected") === "true" && el.textContent?.includes("workspace-b"));
    expect(selectedOption).toBeDefined();
    expect(selectedOption!.textContent).toContain("✓");
  });

  describe("route-based hiding", () => {
    it("renders nothing on /workspaces route", () => {
      const { container } = render(
        <MemoryRouter initialEntries={["/workspaces"]}>
          <WorkspacePicker />
        </MemoryRouter>,
      );
      expect(container.querySelector("[data-testid='workspace-picker']")).toBeNull();
    });

    it("renders nothing on /workspaces/:workspaceName route", () => {
      const { container } = render(
        <MemoryRouter initialEntries={["/workspaces/my-workspace"]}>
          <WorkspacePicker />
        </MemoryRouter>,
      );
      expect(container.querySelector("[data-testid='workspace-picker']")).toBeNull();
    });

    it("renders normally on non-hidden routes", () => {
      render(
        <MemoryRouter initialEntries={["/experiments"]}>
          <WorkspacePicker />
        </MemoryRouter>,
      );
      expect(screen.getByLabelText("Select workspace")).toBeInTheDocument();
    });
  });
});
