import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ExperimentPermissionsPage from "./experiment-permissions-page";

import type {
  EntityPermission,
  ExperimentListItem,
  PermissionType,
} from "../../shared/types/entity";
import type { Mock } from "vitest";

interface EntityPermissionsManagerProps {
  resourceId: string;
  resourceName: string;
  resourceType: PermissionType;
  permissions: EntityPermission[];
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
}

const mockUseExperimentUserPermissions: Mock<
  () => {
    experimentUserPermissions: EntityPermission[];
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
  }
> = vi.fn();

const mockUseExperimentGroupPermissions: Mock<
  () => {
    experimentGroupPermissions: EntityPermission[];
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
  }
> = vi.fn();

const mockUseAllExperiments: Mock<
  () => {
    allExperiments: ExperimentListItem[] | null;
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
  }
> = vi.fn();

const mockEntityPermissionsManager: Mock<
  (props: EntityPermissionsManagerProps) => void
> = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => ({ experimentId: "123" }),
}));

vi.mock("../../core/hooks/use-experiment-user-permissions", () => ({
  useExperimentUserPermissions: () => mockUseExperimentUserPermissions(),
}));

vi.mock("../../core/hooks/use-experiment-group-permissions", () => ({
  useExperimentGroupPermissions: () => mockUseExperimentGroupPermissions(),
}));

vi.mock("../../core/hooks/use-all-experiments", () => ({
  useAllExperiments: () => mockUseAllExperiments(),
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
  EntityPermissionsManager: (props: EntityPermissionsManagerProps) => {
    mockEntityPermissionsManager(props);
    return <div data-testid="permissions-manager" />;
  },
}));

describe("ExperimentPermissionsPage", () => {
  beforeEach(() => {
    mockUseExperimentUserPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      experimentUserPermissions: [],
    });
    mockUseExperimentGroupPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      experimentGroupPermissions: [],
    });
    mockUseAllExperiments.mockReturnValue({
      allExperiments: [{ id: "123", name: "Test Experiment", tags: {} }],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
  });

  it("renders correctly", () => {
    render(<ExperimentPermissionsPage />);

    expect(screen.getByTestId("page-container")).toHaveAttribute(
      "title",
      "Permissions for Experiment Test Experiment",
    );
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("combines permissions and passes to manager", () => {
    mockUseExperimentUserPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      experimentUserPermissions: [
        { name: "u1", kind: "user", permission: "EDIT" },
      ],
    });
    mockUseExperimentGroupPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      experimentGroupPermissions: [
        { name: "g1", kind: "group", permission: "MANAGE" },
      ],
    });

    render(<ExperimentPermissionsPage />);

    const lastCall =
      mockEntityPermissionsManager.mock.calls[
        mockEntityPermissionsManager.mock.calls.length - 1
      ][0];
    expect(lastCall.permissions).toHaveLength(2);
    expect(lastCall.permissions).toEqual(
      expect.arrayContaining([
        { name: "u1", kind: "user", permission: "EDIT" },
        { name: "g1", kind: "group", permission: "MANAGE" },
      ]),
    );
  });

  it("shows loading state when user permissions are loading", () => {
    mockUseExperimentUserPermissions.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      experimentUserPermissions: [],
    });

    render(<ExperimentPermissionsPage />);

    const lastCall =
      mockEntityPermissionsManager.mock.calls[
        mockEntityPermissionsManager.mock.calls.length - 1
      ][0];
    expect(lastCall.isLoading).toBe(true);
  });

  it("shows loading state when group permissions are loading", () => {
    mockUseExperimentGroupPermissions.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      experimentGroupPermissions: [],
    });

    render(<ExperimentPermissionsPage />);

    const lastCall =
      mockEntityPermissionsManager.mock.calls[
        mockEntityPermissionsManager.mock.calls.length - 1
      ][0];
    expect(lastCall.isLoading).toBe(true);
  });

  it("shows error when user permissions have error", () => {
    const error = new Error("User permission error");
    mockUseExperimentUserPermissions.mockReturnValue({
      isLoading: false,
      error,
      refresh: vi.fn(),
      experimentUserPermissions: [],
    });

    render(<ExperimentPermissionsPage />);

    const lastCall =
      mockEntityPermissionsManager.mock.calls[
        mockEntityPermissionsManager.mock.calls.length - 1
      ][0];
    expect(lastCall.error).toBe(error);
  });

  it("shows error when group permissions have error", () => {
    const error = new Error("Group permission error");
    mockUseExperimentGroupPermissions.mockReturnValue({
      isLoading: false,
      error,
      refresh: vi.fn(),
      experimentGroupPermissions: [],
    });

    render(<ExperimentPermissionsPage />);

    const lastCall =
      mockEntityPermissionsManager.mock.calls[
        mockEntityPermissionsManager.mock.calls.length - 1
      ][0];
    expect(lastCall.error).toBe(error);
  });

  it("calls both refresh functions when refresh is called", () => {
    const refreshUser = vi.fn();
    const refreshGroup = vi.fn();

    mockUseExperimentUserPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: refreshUser,
      experimentUserPermissions: [],
    });
    mockUseExperimentGroupPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: refreshGroup,
      experimentGroupPermissions: [],
    });

    render(<ExperimentPermissionsPage />);

    const lastCall =
      mockEntityPermissionsManager.mock.calls[
        mockEntityPermissionsManager.mock.calls.length - 1
      ][0];
    lastCall.refresh();

    expect(refreshUser).toHaveBeenCalled();
    expect(refreshGroup).toHaveBeenCalled();
  });

  it("uses experiment ID when experiment name is not found", () => {
    mockUseAllExperiments.mockReturnValue({
      allExperiments: [],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<ExperimentPermissionsPage />);

    expect(screen.getByTestId("page-container")).toHaveAttribute(
      "title",
      "Permissions for Experiment 123",
    );
  });
});
