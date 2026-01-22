import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DeleteWebhookModal } from "./delete-webhook-modal";
import type { Webhook } from "../../../shared/types/entity";

describe("DeleteWebhookModal", () => {
  const mockWebhook: Webhook = {
    webhook_id: "123",
    name: "Test Webhook",
    url: "https://example.com",
    events: ["event1"],
    status: "ACTIVE",
    creation_timestamp: 123456789,
    last_updated_timestamp: 123456789,
  };

  it("renders correctly when open and has a webhook", () => {
    render(
      <DeleteWebhookModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        webhook={mockWebhook}
        isProcessing={false}
      />
    );

    expect(screen.getByText("Delete Webhook")).toBeInTheDocument();
    expect(screen.getByText("Test Webhook")).toBeInTheDocument();
    expect(screen.getByText("123")).toBeInTheDocument();
    expect(screen.getByText("https://example.com")).toBeInTheDocument();
  });

  it("calls onConfirm when Delete button is clicked", () => {
    const mockOnConfirm = vi.fn();
    render(
      <DeleteWebhookModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={mockOnConfirm}
        webhook={mockWebhook}
        isProcessing={false}
      />
    );

    fireEvent.click(screen.getByText("Delete Permanently"));
    expect(mockOnConfirm).toHaveBeenCalled();
  });

  it("disables buttons when processing", () => {
    render(
      <DeleteWebhookModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        webhook={mockWebhook}
        isProcessing={true}
      />
    );

    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("returns null when webhook is null", () => {
    const { container } = render(
      <DeleteWebhookModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        webhook={null}
        isProcessing={false}
      />
    );

    expect(container.firstChild).toBeNull();
  });
});
