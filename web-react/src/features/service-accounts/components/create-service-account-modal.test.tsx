import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CreateServiceAccountModal } from "./create-service-account-modal";

describe("CreateServiceAccountModal", () => {
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();

  it("renders when open", () => {
    render(
      <CreateServiceAccountModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
      />,
    );
    expect(screen.getByText("Create Service Account")).toBeDefined();
  });

  it("handles form inputs and submission", async () => {
    render(
      <CreateServiceAccountModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
      />,
    );

    const nameInput = screen.getByLabelText(/Service Account Name/i);
    const displayNameInput = screen.getByLabelText(/Display Name/i);
    const isAdminCheckbox = screen.getByLabelText(/Grant Admin Privileges/i);
    const saveButton = screen.getByRole("button", { name: /Save/i });

    expect(saveButton).toBeDisabled();

    fireEvent.change(nameInput, { target: { value: "test-sa" } });
    // Display name should auto-fill if not manual
    expect((displayNameInput as HTMLInputElement).value).toBe("test-sa");

    fireEvent.click(isAdminCheckbox);
    expect(saveButton).not.toBeDisabled();

    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith({
        name: "test-sa",
        display_name: "test-sa",
        is_admin: true,
      });
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it("allows manual display name change", () => {
    render(
      <CreateServiceAccountModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
      />,
    );

    const nameInput = screen.getByLabelText(/Service Account Name/i);
    const displayNameInput = screen.getByLabelText(/Display Name/i);

    fireEvent.change(displayNameInput, { target: { value: "Manual Name" } });
    fireEvent.change(nameInput, { target: { value: "test-sa" } });

    expect((displayNameInput as HTMLInputElement).value).toBe("Manual Name");
  });
});
