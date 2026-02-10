import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { EditWebhookModal } from "./edit-webhook-modal";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import * as webhookServiceModule from "../../../core/services/webhook-service";
import type { Webhook } from "../../../shared/types/entity";

vi.mock("../../../shared/components/toast/use-toast");
vi.mock("../../../core/services/webhook-service");

describe("EditWebhookModal", () => {
  const mockShowToast = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();
  const mockWebhook: Webhook = {
    webhook_id: "wh-1",
    name: "Old Name",
    url: "https://old-url.com",
    events: ["prompt.created"],
    status: "ACTIVE",
    creation_timestamp: 123456789,
    last_updated_timestamp: 123456789,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as unknown as ReturnType<typeof useToastModule.useToast>);
  });

  it("renders correctly with webhook data when open", async () => {
    render(
      <EditWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        webhook={mockWebhook}
      />,
    );

    expect(await screen.findByText("Edit Webhook")).toBeInTheDocument();
    expect(screen.getByLabelText(/Name/)).toHaveValue("Old Name");
    expect(screen.getByLabelText(/URL/)).toHaveValue("https://old-url.com");
  });

  it("calls updateWebhook and onSuccess on successful submission", async () => {
    const mockUpdateWebhook = vi.spyOn(webhookServiceModule, "updateWebhook");
    mockUpdateWebhook.mockResolvedValue({} as unknown as Webhook);

    render(
      <EditWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        webhook={mockWebhook}
      />,
    );

    await screen.findByDisplayValue("Old Name");

    fireEvent.change(screen.getByLabelText(/Name/), {
      target: { value: "New Name" },
    });

    fireEvent.click(screen.getByText("Update"));

    await waitFor(() => {
      expect(mockUpdateWebhook).toHaveBeenCalledWith(
        "wh-1",
        expect.objectContaining({
          name: "New Name",
        }),
      );
      expect(mockShowToast).toHaveBeenCalled();
      expect(mockOnSuccess).toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalled();
    });
  });
});
