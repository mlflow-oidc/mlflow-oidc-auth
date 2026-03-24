import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { BulkAssignModal } from "./bulk-assign-modal";

const mockShowToast = vi.fn();

vi.mock("../../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

vi.mock("../../../shared/components/modal", () => ({
  Modal: ({ children, isOpen, title }: { children: React.ReactNode; isOpen: boolean; title: string }) =>
    isOpen ? (
      <div data-testid="modal" title={title}>
        {children}
      </div>
    ) : null,
}));

vi.mock("../../../shared/components/permission-level-select", () => ({
  PermissionLevelSelect: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <select data-testid="permission-select" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="READ">READ</option>
      <option value="EDIT">EDIT</option>
      <option value="MANAGE">MANAGE</option>
    </select>
  ),
}));

vi.mock("../../../shared/components/button", () => ({
  Button: ({ children, onClick, disabled, variant }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean; variant?: string }) => (
    <button onClick={onClick} disabled={disabled} data-variant={variant}>
      {children}
    </button>
  ),
}));

describe("BulkAssignModal", () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onGrant: vi.fn().mockResolvedValue(true),
    onSuccess: vi.fn(),
    title: "Bulk Assign Users",
    nameLabel: "Usernames",
    namePlaceholder: "user1, user2, user3",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    defaultProps.onClose = vi.fn();
    defaultProps.onGrant = vi.fn().mockResolvedValue(true);
    defaultProps.onSuccess = vi.fn();
  });

  it("renders modal with textarea and permission select when open", () => {
    render(<BulkAssignModal {...defaultProps} />);

    expect(screen.getByTestId("modal")).toBeInTheDocument();
    expect(screen.getByText("Usernames*")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("user1, user2, user3")).toBeInTheDocument();
    expect(screen.getByTestId("permission-select")).toBeInTheDocument();
    expect(screen.getByText("Assign All")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("does not render content when not open", () => {
    render(<BulkAssignModal {...defaultProps} isOpen={false} />);

    expect(screen.queryByTestId("modal")).not.toBeInTheDocument();
  });

  it("parses comma-separated names correctly and calls onGrant for each", async () => {
    render(<BulkAssignModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText("user1, user2, user3");
    await userEvent.type(textarea, "alice, bob, charlie");

    fireEvent.click(screen.getByText("Assign All"));

    await waitFor(() => {
      expect(defaultProps.onGrant).toHaveBeenCalledTimes(3);
      expect(defaultProps.onGrant).toHaveBeenCalledWith("alice", "READ");
      expect(defaultProps.onGrant).toHaveBeenCalledWith("bob", "READ");
      expect(defaultProps.onGrant).toHaveBeenCalledWith("charlie", "READ");
    });
  });

  it("parses newline-separated names correctly", async () => {
    render(<BulkAssignModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText("user1, user2, user3");
    fireEvent.change(textarea, { target: { value: "alice\nbob\ncharlie" } });

    fireEvent.click(screen.getByText("Assign All"));

    await waitFor(() => {
      expect(defaultProps.onGrant).toHaveBeenCalledTimes(3);
      expect(defaultProps.onGrant).toHaveBeenCalledWith("alice", "READ");
      expect(defaultProps.onGrant).toHaveBeenCalledWith("bob", "READ");
      expect(defaultProps.onGrant).toHaveBeenCalledWith("charlie", "READ");
    });
  });

  it("trims whitespace and deduplicates names", async () => {
    render(<BulkAssignModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText("user1, user2, user3");
    fireEvent.change(textarea, { target: { value: "  alice ,  bob  , alice , bob  " } });

    fireEvent.click(screen.getByText("Assign All"));

    await waitFor(() => {
      expect(defaultProps.onGrant).toHaveBeenCalledTimes(2);
      expect(defaultProps.onGrant).toHaveBeenCalledWith("alice", "READ");
      expect(defaultProps.onGrant).toHaveBeenCalledWith("bob", "READ");
    });
  });

  it("shows success toast when all grants succeed", async () => {
    defaultProps.onGrant.mockResolvedValue(true);

    render(<BulkAssignModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText("user1, user2, user3");
    fireEvent.change(textarea, { target: { value: "alice, bob" } });

    fireEvent.click(screen.getByText("Assign All"));

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith("Successfully assigned 2 permissions", "success");
    });
  });

  it("shows error summary when some grants fail", async () => {
    defaultProps.onGrant.mockImplementation((name: string) => Promise.resolve(name !== "bob"));

    render(<BulkAssignModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText("user1, user2, user3");
    fireEvent.change(textarea, { target: { value: "alice, bob, charlie" } });

    fireEvent.click(screen.getByText("Assign All"));

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith("2 assigned, 1 failed", "error");
      expect(screen.getByText(/✗ 1 failed: bob/)).toBeInTheDocument();
      expect(screen.getByText(/✓ 2 assigned successfully/)).toBeInTheDocument();
    });
  });

  it("disables Assign All button when textarea is empty", () => {
    render(<BulkAssignModal {...defaultProps} />);

    const assignButton = screen.getByText("Assign All");
    expect(assignButton).toBeDisabled();
  });

  it("calls onSuccess and onClose when all succeed", async () => {
    defaultProps.onGrant.mockResolvedValue(true);

    render(<BulkAssignModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText("user1, user2, user3");
    fireEvent.change(textarea, { target: { value: "alice" } });

    fireEvent.click(screen.getByText("Assign All"));

    await waitFor(() => {
      expect(defaultProps.onSuccess).toHaveBeenCalled();
      expect(defaultProps.onClose).toHaveBeenCalled();
    });
  });

  it("calls onSuccess but keeps modal open when some fail", async () => {
    defaultProps.onGrant.mockImplementation((name: string) => Promise.resolve(name !== "bob"));

    render(<BulkAssignModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText("user1, user2, user3");
    fireEvent.change(textarea, { target: { value: "alice, bob" } });

    fireEvent.click(screen.getByText("Assign All"));

    await waitFor(() => {
      expect(defaultProps.onSuccess).toHaveBeenCalled();
      expect(defaultProps.onClose).not.toHaveBeenCalled();
      expect(screen.getByTestId("modal")).toBeInTheDocument();
    });
  });

  it("shows no names provided toast when textarea is whitespace only", async () => {
    render(<BulkAssignModal {...defaultProps} />);

    const textarea = screen.getByPlaceholderText("user1, user2, user3");
    fireEvent.change(textarea, { target: { value: "  ,  , \n  " } });

    fireEvent.click(screen.getByText("Assign All"));

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith("No names provided", "error");
      expect(defaultProps.onGrant).not.toHaveBeenCalled();
    });
  });
});
