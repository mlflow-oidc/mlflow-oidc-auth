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
        service_account_source: "internal",
      });
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it("creates an external account bound to a provider and subject", async () => {
    render(
      <CreateServiceAccountModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        sources={[
          {
            id: "internal",
            display_name: "Internal (issued access tokens only)",
            type: "internal",
          },
          { id: "ci", display_name: "CI workloads", type: "oidc" },
        ]}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Service Account Name/i), {
      target: { value: "ci-bot" },
    });
    fireEvent.change(screen.getByLabelText("Signs in with"), {
      target: { value: "ci" },
    });
    fireEvent.change(screen.getByLabelText("Subject (optional)"), {
      target: { value: "repo:o/a:ref:main" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Save/i }));

    await waitFor(() =>
      expect(mockOnSave).toHaveBeenCalledWith({
        name: "ci-bot",
        display_name: "ci-bot",
        is_admin: false,
        service_account_source: "ci",
        subject: "repo:o/a:ref:main",
      }),
    );
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
