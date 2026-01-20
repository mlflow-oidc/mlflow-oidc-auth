import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CreateWebhookModal } from "./create-webhook-modal";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import * as webhookServiceModule from "../../../core/services/webhook-service";

vi.mock("../../../shared/components/toast/use-toast");
vi.mock("../../../core/services/webhook-service");

describe("CreateWebhookModal", () => {
  const mockShowToast = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as any);
  });

  it("renders correctly when open", () => {
    render(
      <CreateWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    expect(screen.getByText("Create webhook")).toBeInTheDocument();
    expect(screen.getByLabelText("Name*")).toBeInTheDocument();
    expect(screen.getByLabelText("URL*")).toBeInTheDocument();
    expect(screen.getByText("Events*")).toBeInTheDocument();
  });

  it("validation fails if required fields are empty", async () => {
    const { container } = render(
      <CreateWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() => {
      expect(screen.getByText("Name is required")).toBeInTheDocument();
      expect(screen.getByText("URL is required")).toBeInTheDocument();
      expect(screen.getByText("At least one event must be selected")).toBeInTheDocument();
    });
  });

  it("validation fails for invalid URL", async () => {
    render(
      <CreateWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    fireEvent.change(screen.getByLabelText("Name*"), { target: { value: "Test Webhook" } });
    fireEvent.change(screen.getByLabelText("URL*"), { target: { value: "invalid-url" } });
    
    fireEvent.click(screen.getByText("Create"));

    expect(screen.getByText("Invalid URL format")).toBeInTheDocument();
  });

  it("calls createWebhook and onSuccess on successful submission", async () => {
    vi.spyOn(webhookServiceModule, "createWebhook").mockResolvedValue({} as any);

    render(
      <CreateWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    fireEvent.change(screen.getByLabelText("Name*"), { target: { value: "Test Webhook" } });
    fireEvent.change(screen.getByLabelText("URL*"), { target: { value: "https://example.com" } });
    
    // Select an event
    fireEvent.click(screen.getByText("registered_model.created"));

    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(webhookServiceModule.createWebhook).toHaveBeenCalledWith({
        name: "Test Webhook",
        url: "https://example.com",
        events: ["registered_model.created"],
        secret: "",
      });
      expect(mockShowToast).toHaveBeenCalledWith("Webhook created successfully", "success");
      expect(mockOnSuccess).toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it("trims trailing spaces from fields before submission", async () => {
    vi.spyOn(webhookServiceModule, "createWebhook").mockResolvedValue({} as any);

    render(
      <CreateWebhookModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    fireEvent.change(screen.getByLabelText("Name*"), { target: { value: "  Test Webhook  " } });
    fireEvent.change(screen.getByLabelText("URL*"), { target: { value: "  https://example.com  " } });
    fireEvent.change(screen.getByLabelText("Secret (Optional)"), { target: { value: "  mysecret  " } });
    
    // Select an event
    fireEvent.click(screen.getByText("registered_model.created"));

    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(webhookServiceModule.createWebhook).toHaveBeenCalledWith({
        name: "Test Webhook",
        url: "https://example.com",
        events: ["registered_model.created"],
        secret: "mysecret",
      });
      expect(mockShowToast).toHaveBeenCalledWith("Webhook created successfully", "success");
    });
  });
});
