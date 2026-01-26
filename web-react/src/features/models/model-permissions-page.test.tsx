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
});
