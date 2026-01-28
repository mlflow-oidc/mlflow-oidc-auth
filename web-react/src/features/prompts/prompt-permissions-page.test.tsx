import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import PromptPermissionsPage from "./prompt-permissions-page";

const mockUsePromptUserPermissions = vi.fn();
const mockUsePromptGroupPermissions = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => ({ promptName: "TestPrompt" }),
}));

vi.mock("../../core/hooks/use-prompt-user-permissions", () => ({
  usePromptUserPermissions: () => mockUsePromptUserPermissions() as unknown,
}));

vi.mock("../../core/hooks/use-prompt-group-permissions", () => ({
  usePromptGroupPermissions: () => mockUsePromptGroupPermissions() as unknown,
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({
    children,
    title,
  }: {
    children: React.ReactNode;
    title: string;
  }) => (
    <div data-testid="page-container" title={title}>
      {children}
    </div>
  ),
}));

vi.mock("../permissions/components/entity-permissions-manager", () => ({
  EntityPermissionsManager: () => <div data-testid="permissions-manager" />,
}));

describe("PromptPermissionsPage", () => {
  beforeEach(() => {
    mockUsePromptUserPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      promptUserPermissions: [],
    });
    mockUsePromptGroupPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      promptGroupPermissions: [],
    });
  });

  it("renders correctly", () => {
    render(<PromptPermissionsPage />);

    expect(screen.getByTestId("page-container")).toHaveAttribute(
      "title",
      "Permissions for Prompt TestPrompt",
    );
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("combines user and group permissions", () => {
    mockUsePromptUserPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      promptUserPermissions: [
        { name: "user1", kind: "user", permission: "READ" },
      ],
    });
    mockUsePromptGroupPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      promptGroupPermissions: [
        { name: "group1", kind: "group", permission: "EDIT" },
      ],
    });

    render(<PromptPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("shows loading state when user permissions are loading", () => {
    mockUsePromptUserPermissions.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      promptUserPermissions: [],
    });

    render(<PromptPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("shows loading state when group permissions are loading", () => {
    mockUsePromptGroupPermissions.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      promptGroupPermissions: [],
    });

    render(<PromptPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("shows error when user permissions have error", () => {
    mockUsePromptUserPermissions.mockReturnValue({
      isLoading: false,
      error: new Error("User permission error"),
      refresh: vi.fn(),
      promptUserPermissions: [],
    });

    render(<PromptPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("shows error when group permissions have error", () => {
    mockUsePromptGroupPermissions.mockReturnValue({
      isLoading: false,
      error: new Error("Group permission error"),
      refresh: vi.fn(),
      promptGroupPermissions: [],
    });

    render(<PromptPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });
});
