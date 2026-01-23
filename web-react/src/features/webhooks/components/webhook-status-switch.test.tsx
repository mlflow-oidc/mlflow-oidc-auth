import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { WebhookStatusSwitch } from "./webhook-status-switch";
import * as useUpdateWebhookModule from "../../../core/hooks/use-update-webhook";
import type { Webhook } from "../../../shared/types/entity";

vi.mock("../../../core/hooks/use-update-webhook");

describe("WebhookStatusSwitch", () => {
  const mockUpdate = vi.fn();
  const mockOnSuccess = vi.fn();

  const mockWebhook: Webhook = {
    webhook_id: "1",
    name: "Test Hook",
    url: "http://example.com",
    events: [],
    status: "ACTIVE",
    creation_timestamp: 0,
    last_updated_timestamp: 0,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useUpdateWebhookModule, "useUpdateWebhook").mockReturnValue({
      update: mockUpdate,
      isUpdating: false,
    });
  });

  it("renders correctly with initial status", () => {
    render(<WebhookStatusSwitch webhook={mockWebhook} onSuccess={mockOnSuccess} />);
    expect(screen.getByRole("switch")).toBeChecked();
  });

  it("toggles status and calls update on click", async () => {
    mockUpdate.mockResolvedValue(true);

    render(<WebhookStatusSwitch webhook={mockWebhook} onSuccess={mockOnSuccess} />);

    const switchEl = screen.getByRole("switch");
    fireEvent.click(switchEl);

    // Optimistic update check
    expect(mockUpdate).toHaveBeenCalledWith(
      "1",
      { status: "DISABLED" },
      expect.objectContaining({
        onSuccessMessage: expect.stringContaining("disabled"),
      })
    );

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalledWith("DISABLED");
    });
  });

  it("reverts status if update fails", async () => {
    mockUpdate.mockResolvedValue(false);

    render(<WebhookStatusSwitch webhook={mockWebhook} onSuccess={mockOnSuccess} />);

    const switchEl = screen.getByRole("switch");

    // Initial state: Checked (ACTIVE)
    expect(switchEl).toBeChecked();

    fireEvent.click(switchEl);

    // Expect API call
    expect(mockUpdate).toHaveBeenCalled();

    // Should revert to checked after failure
    await waitFor(() => {
      expect(switchEl).toBeChecked();
      expect(mockOnSuccess).not.toHaveBeenCalled();
    });
  });

  it("is disabled when updating", () => {
    vi.spyOn(useUpdateWebhookModule, "useUpdateWebhook").mockReturnValue({
      update: mockUpdate,
      isUpdating: true,
    });

    render(<WebhookStatusSwitch webhook={mockWebhook} />);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-disabled", "true");
  });
});
