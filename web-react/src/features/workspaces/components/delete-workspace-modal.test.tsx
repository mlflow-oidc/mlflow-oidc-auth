import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DeleteWorkspaceModal } from "./delete-workspace-modal";

describe("DeleteWorkspaceModal", () => {
  const mockWorkspace = { name: "test-ws", description: "A test workspace" };

  it("returns null when workspace is null", () => {
    const { container } = render(
      <DeleteWorkspaceModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        workspace={null}
        isProcessing={false}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders correctly when open with workspace", () => {
    render(
      <DeleteWorkspaceModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        workspace={mockWorkspace}
        isProcessing={false}
      />,
    );

    expect(screen.getByText("Delete Workspace")).toBeInTheDocument();
    expect(screen.getByText("test-ws")).toBeInTheDocument();
    expect(
      screen.getByText(
        "All associated permissions will be removed. This action cannot be undone.",
      ),
    ).toBeInTheDocument();
  });

  it("calls onConfirm when Delete button is clicked", () => {
    const mockOnConfirm = vi.fn();
    render(
      <DeleteWorkspaceModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={mockOnConfirm}
        workspace={mockWorkspace}
        isProcessing={false}
      />,
    );

    fireEvent.click(screen.getByText("Delete Permanently"));
    expect(mockOnConfirm).toHaveBeenCalled();
  });

  it("disables buttons when processing", () => {
    render(
      <DeleteWorkspaceModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        workspace={mockWorkspace}
        isProcessing={true}
      />,
    );

    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("shows warning and disables delete for default workspace", () => {
    const defaultWorkspace = { name: "default", description: "" };
    render(
      <DeleteWorkspaceModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        workspace={defaultWorkspace}
        isProcessing={false}
      />,
    );

    expect(
      screen.getByText("The default workspace cannot be deleted."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete Permanently" }),
    ).toBeDisabled();
  });

  it("calls onClose when Cancel is clicked", () => {
    const mockOnClose = vi.fn();
    render(
      <DeleteWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onConfirm={vi.fn()}
        workspace={mockWorkspace}
        isProcessing={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
