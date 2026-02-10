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
    render(
      <WebhookStatusSwitch webhook={mockWebhook} onSuccess={mockOnSuccess} />,
    );
    expect(screen.getByRole("switch")).toBeChecked();
  });

  it("toggles status and calls update on click", async () => {
    mockUpdate.mockResolvedValue(true);

    render(
      <WebhookStatusSwitch webhook={mockWebhook} onSuccess={mockOnSuccess} />,
    );

    const switchEl = screen.getByRole("switch");
    fireEvent.click(switchEl);

    expect(mockUpdate).toHaveBeenCalledWith(
      "1",
      expect.objectContaining({ status: "DISABLED" }),
      expect.anything(),
    );

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalledWith("DISABLED");
    });
  });
});
