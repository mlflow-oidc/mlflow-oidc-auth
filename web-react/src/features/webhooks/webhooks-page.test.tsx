import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import WebhooksPage from "./webhooks-page";
import * as useWebhooksModule from "../../core/hooks/use-webhooks";
import * as useSearchModule from "../../core/hooks/use-search";
import * as useToastModule from "../../shared/components/toast/use-toast";
import * as webhookService from "../../core/services/webhook-service";

vi.mock("../../core/hooks/use-webhooks");
vi.mock("../../core/hooks/use-search");
vi.mock("../../shared/components/toast/use-toast");
vi.mock("../../core/services/webhook-service");

describe("WebhooksPage", () => {
  const mockWebhooks = [
    { webhook_id: "1", name: "Webhook 1", url: "http://example.com/1" },
    { webhook_id: "2", name: "Webhook 2", url: "http://example.com/2" },
  ];

  const mockShowToast = vi.fn();
  const mockRefresh = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useWebhooksModule, "useWebhooks").mockReturnValue({
      webhooks: mockWebhooks as any,
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    });

    vi.spyOn(useSearchModule, "useSearch").mockReturnValue({
      searchTerm: "",
      submittedTerm: "",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as any);
  });

  it("renders the page title, webhooks table, and add button", () => {
    render(<WebhooksPage />);
    expect(screen.getByText("Webhooks")).toBeInTheDocument();
    expect(screen.getByText("Webhook 1")).toBeInTheDocument();
    expect(screen.getByText("Webhook 2")).toBeInTheDocument();
    expect(screen.getByText("http://example.com/1")).toBeInTheDocument();
    expect(screen.getByText("Add webhook")).toBeInTheDocument();
  });

  it("opens CreateWebhookModal when Add webhook is clicked", () => {
    render(<WebhooksPage />);
    fireEvent.click(screen.getByText("Add webhook"));
    expect(screen.getByText("Create webhook")).toBeInTheDocument();
  });

  it("calls testWebhook when Test button is clicked", async () => {
    vi.spyOn(webhookService, "testWebhook").mockResolvedValue({
      success: true,
    });

    render(<WebhooksPage />);
    const testButtons = screen.getAllByTitle("Test");
    fireEvent.click(testButtons[0]);

    expect(webhookService.testWebhook).toHaveBeenCalledWith("1");
    await vi.waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        "Test successful for Webhook 1",
        "success"
      );
    });
  });

  it("opens DeleteWebhookModal when Delete button is clicked and can confirm deletion", async () => {
    vi.spyOn(webhookService, "deleteWebhook").mockResolvedValue({
      message: "Deleted",
    });

    render(<WebhooksPage />);
    const deleteButtons = screen.getAllByTitle("Delete");
    fireEvent.click(deleteButtons[0]);

    // Check if modal is open
    expect(screen.getByText("Delete Webhook")).toBeInTheDocument();
    
    // Webhook 1 is in the table and in the modal
    expect(screen.getAllByText("Webhook 1").length).toBeGreaterThan(0);

    // Click permanent delete
    fireEvent.click(screen.getByText("Delete Permanently"));

    expect(webhookService.deleteWebhook).toHaveBeenCalledWith("1");
    await vi.waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        "Webhook \"Webhook 1\" deleted successfully",
        "success"
      );
      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  it("filters webhooks based on search term", () => {
    vi.spyOn(useSearchModule, "useSearch").mockReturnValue({
      searchTerm: "Webhook 1",
      submittedTerm: "Webhook 1",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    render(<WebhooksPage />);
    expect(screen.getByText("Webhook 1")).toBeInTheDocument();
    expect(screen.queryByText("Webhook 2")).not.toBeInTheDocument();
  });
});
