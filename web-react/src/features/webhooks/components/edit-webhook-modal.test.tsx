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
    status: "active",
    creation_timestamp: 123456789,
    last_updated_timestamp: 123456789,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as any);
  });

  it("renders correctly with webhook data when open", async () => {
    render(
      <EditWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        webhook={mockWebhook}
      />
    );

    expect(await screen.findByText("Edit webhook")).toBeInTheDocument();
    expect(screen.getByLabelText(/Name/)).toHaveValue("Old Name");
    expect(screen.getByLabelText(/URL/)).toHaveValue("https://old-url.com");
    expect(screen.getByLabelText("registered_model.created")).not.toBeChecked();
    expect(screen.getByLabelText("prompt.created")).toBeChecked();
  });

  it("validation fails if required fields are empty", async () => {
    render(
      <EditWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        webhook={mockWebhook}
      />
    );

    // Wait for initial population
    await screen.findByDisplayValue("Old Name");

    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText(/URL/), { target: { value: "" } });
    
    // Uncheck the only selected event
    fireEvent.click(screen.getByLabelText("prompt.created"));

    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(screen.getByText("Name is required")).toBeInTheDocument();
      expect(screen.getByText("URL is required")).toBeInTheDocument();
      expect(screen.getByText("At least one event must be selected")).toBeInTheDocument();
    });
  });

  it("validation fails for URL without http or https protocol", async () => {
    render(
      <EditWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        webhook={mockWebhook}
      />
    );

    await screen.findByDisplayValue("Old Name");

    fireEvent.change(screen.getByLabelText(/URL/), { target: { value: "zfzfshttps://echo.technicaldomain.xyz/webhook" } });
    
    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(screen.getByText("Invalid URL format")).toBeInTheDocument();
    });
  });

  it("calls updateWebhook and onSuccess on successful submission", async () => {
    vi.spyOn(webhookServiceModule, "updateWebhook").mockResolvedValue({} as any);

    render(
      <EditWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        webhook={mockWebhook}
      />
    );

    await screen.findByDisplayValue("Old Name");

    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: "New Name" } });
    fireEvent.change(screen.getByLabelText(/URL/), { target: { value: "https://new-url.com" } });
    fireEvent.change(screen.getByLabelText(/Secret/), { target: { value: "new-secret" } });

    fireEvent.click(screen.getByText("Update"));

    await waitFor(() => {
      expect(webhookServiceModule.updateWebhook).toHaveBeenCalledWith("wh-1", {
        name: "New Name",
        url: "https://new-url.com",
        events: ["prompt.created"],
        secret: "new-secret",
      });
      expect(mockShowToast).toHaveBeenCalledWith("Old Name webhook updated successfully", "success");
      expect(mockOnSuccess).toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it("does not send secret if it is empty", async () => {
    vi.spyOn(webhookServiceModule, "updateWebhook").mockResolvedValue({} as any);

    render(
      <EditWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
        webhook={mockWebhook}
      />
    );

    await screen.findByDisplayValue("Old Name");

    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: "New Name" } });

    fireEvent.click(screen.getByText("Update"));

    await waitFor(() => {
      expect(webhookServiceModule.updateWebhook).toHaveBeenCalledWith("wh-1", {
        name: "New Name",
        url: "https://old-url.com",
        events: ["prompt.created"],
        // secret should NOT be present
      });
      expect(webhookServiceModule.updateWebhook).not.toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ secret: expect.anything() }));
    });
  });
});
