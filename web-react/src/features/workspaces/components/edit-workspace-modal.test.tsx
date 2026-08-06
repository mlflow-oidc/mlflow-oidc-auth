import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { EditWorkspaceModal } from "./edit-workspace-modal";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import * as workspaceServiceModule from "../../../core/services/workspace-service";

vi.mock("../../../shared/components/toast/use-toast");
vi.mock("../../../core/services/workspace-service");

describe("EditWorkspaceModal", () => {
  const mockShowToast = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();
  const mockWorkspace = {
    name: "test-ws",
    description: "Original desc",
    default_artifact_root: "s3://original-bucket",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as unknown as ReturnType<typeof useToastModule.useToast>);
  });

  it("returns null when workspace is null", () => {
    const { container } = render(
      <EditWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        workspace={null}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders correctly when open with workspace", () => {
    render(
      <EditWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        workspace={mockWorkspace}
      />,
    );

    expect(screen.getByText("Edit Workspace")).toBeInTheDocument();
    expect(screen.getByDisplayValue("test-ws")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Original desc")).toBeInTheDocument();
    expect(
      screen.getByDisplayValue("s3://original-bucket"),
    ).toBeInTheDocument();
  });

  it("has name field as read-only/disabled", () => {
    render(
      <EditWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        workspace={mockWorkspace}
      />,
    );

    const nameInput = screen.getByDisplayValue("test-ws");
    expect(nameInput).toBeDisabled();
  });

  it("calls updateWorkspace on submit", async () => {
    const mockUpdateWorkspace = vi.spyOn(
      workspaceServiceModule,
      "updateWorkspace",
    );
    mockUpdateWorkspace.mockResolvedValue({
      name: "test-ws",
      description: "Updated desc",
      default_artifact_root: "s3://original-bucket",
    });

    render(
      <EditWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        workspace={mockWorkspace}
      />,
    );

    const descInput = screen.getByDisplayValue("Original desc");
    fireEvent.change(descInput, { target: { value: "Updated desc" } });
    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(mockUpdateWorkspace).toHaveBeenCalledWith("test-ws", {
        description: "Updated desc",
        default_artifact_root: "s3://original-bucket",
      });
      expect(mockShowToast).toHaveBeenCalledWith(
        "Workspace updated successfully",
        "success",
      );
      expect(mockOnSuccess).toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it("updates default_artifact_root on submit", async () => {
    const mockUpdateWorkspace = vi.spyOn(
      workspaceServiceModule,
      "updateWorkspace",
    );
    mockUpdateWorkspace.mockResolvedValue({
      name: "test-ws",
      description: "Original desc",
      default_artifact_root: "s3://new-bucket",
    });

    render(
      <EditWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        workspace={mockWorkspace}
      />,
    );

    const artifactInput = screen.getByDisplayValue("s3://original-bucket");
    fireEvent.change(artifactInput, {
      target: { value: "s3://new-bucket" },
    });
    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(mockUpdateWorkspace).toHaveBeenCalledWith("test-ws", {
        description: "Original desc",
        default_artifact_root: "s3://new-bucket",
      });
    });
  });

  it("shows error toast on update failure", async () => {
    const mockUpdateWorkspace = vi.spyOn(
      workspaceServiceModule,
      "updateWorkspace",
    );
    mockUpdateWorkspace.mockRejectedValue(new Error("Server error"));

    render(
      <EditWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        workspace={mockWorkspace}
      />,
    );

    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        "Failed to update workspace",
        "error",
      );
    });
  });

  it("calls onClose when Cancel is clicked", () => {
    render(
      <EditWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        workspace={mockWorkspace}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
