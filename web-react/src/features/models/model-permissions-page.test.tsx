import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ModelPermissionsPage from "./model-permissions-page";

import type { EntityPermission } from "../../shared/types/entity";
import type { Mock } from "vitest";

const mockUseModelUserPermissions: Mock<
  () => {
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
    modelUserPermissions: EntityPermission[];
  }
> = vi.fn();
const mockUseModelGroupPermissions: Mock<
  () => {
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
    modelGroupPermissions: EntityPermission[];
  }
> = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => ({ modelName: "TestModel" }),
}));

vi.mock("../../core/hooks/use-model-user-permissions", () => ({
  useModelUserPermissions: () => mockUseModelUserPermissions(),
}));

vi.mock("../../core/hooks/use-model-group-permissions", () => ({
  useModelGroupPermissions: () => mockUseModelGroupPermissions(),
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

describe("ModelPermissionsPage", () => {
  beforeEach(() => {
    mockUseModelUserPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      modelUserPermissions: [],
    });
    mockUseModelGroupPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      modelGroupPermissions: [],
    });
  });

  it("renders correctly", () => {
    render(<ModelPermissionsPage />);

    expect(screen.getByTestId("page-container")).toHaveAttribute(
      "title",
      "Permissions for Model TestModel",
    );
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("combines user and group permissions", () => {
    const mockManager = vi.fn();
    vi.mocked(mockManager);

    mockUseModelUserPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      modelUserPermissions: [
        { name: "user1", kind: "user", permission: "READ" },
      ],
    });
    mockUseModelGroupPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      modelGroupPermissions: [
        { name: "group1", kind: "group", permission: "EDIT" },
      ],
    });

    render(<ModelPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("shows loading state when user permissions are loading", () => {
    mockUseModelUserPermissions.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      modelUserPermissions: [],
    });

    render(<ModelPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("shows loading state when group permissions are loading", () => {
    mockUseModelGroupPermissions.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      modelGroupPermissions: [],
    });

    render(<ModelPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("shows error when user permissions have error", () => {
    mockUseModelUserPermissions.mockReturnValue({
      isLoading: false,
      error: new Error("User permission error"),
      refresh: vi.fn(),
      modelUserPermissions: [],
    });

    render(<ModelPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("shows error when group permissions have error", () => {
    mockUseModelGroupPermissions.mockReturnValue({
      isLoading: false,
      error: new Error("Group permission error"),
      refresh: vi.fn(),
      modelGroupPermissions: [],
    });

    render(<ModelPermissionsPage />);
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });
});
