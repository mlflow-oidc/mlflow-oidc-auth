import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ExperimentPermissionsPage from "./experiment-permissions-page";

const mockUseExperimentUserPermissions = vi.fn();
const mockUseExperimentGroupPermissions = vi.fn();
const mockUseAllExperiments = vi.fn();
const mockEntityPermissionsManager = vi.fn();

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
  EntityPermissionsManager: (props: any) => {
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
      allExperiments: [{ id: "123", name: "Test Experiment" }],
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
      experimentUserPermissions: [{ user: "u1" }],
    });
    mockUseExperimentGroupPermissions.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      experimentGroupPermissions: [{ group: "g1" }],
    });

    render(<ExperimentPermissionsPage />);

    const lastCall =
      mockEntityPermissionsManager.mock.calls[
        mockEntityPermissionsManager.mock.calls.length - 1
      ][0];
    expect(lastCall.permissions).toHaveLength(2);
    expect(lastCall.permissions).toEqual(
      expect.arrayContaining([{ user: "u1" }, { group: "g1" }]),
    );
  });
});
