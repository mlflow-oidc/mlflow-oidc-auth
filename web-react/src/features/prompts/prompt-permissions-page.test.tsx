import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import PromptPermissionsPage from "./prompt-permissions-page";

const mockUsePromptUserPermissions = vi.fn();
const mockUsePromptGroupPermissions = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => ({ promptName: "TestPrompt" }),
}));

vi.mock("../../core/hooks/use-prompt-user-permissions", () => ({
  usePromptUserPermissions: () => mockUsePromptUserPermissions(),
}));

vi.mock("../../core/hooks/use-prompt-group-permissions", () => ({
  usePromptGroupPermissions: () => mockUsePromptGroupPermissions(),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
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
    
    expect(screen.getByTestId("page-container")).toHaveAttribute("title", "Permissions for Prompt TestPrompt");
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });
});
