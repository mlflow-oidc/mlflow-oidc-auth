import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import WebhooksPage from "./webhooks-page";
import * as useWebhooksModule from "../../core/hooks/use-webhooks";
import * as useSearchModule from "../../core/hooks/use-search";
import * as useToastModule from "../../shared/components/toast/use-toast";
import * as webhookService from "../../core/services/webhook-service";
import type { Webhook } from "../../shared/types/entity";

vi.mock("../../core/hooks/use-webhooks");
vi.mock("../../core/hooks/use-search");
vi.mock("../../shared/components/toast/use-toast");
vi.mock("../../core/services/webhook-service");

describe("WebhooksPage", () => {
  const mockWebhooks: Webhook[] = [
    {
      webhook_id: "1",
      name: "Webhook 1",
      url: "http://example.com/1",
      events: ["prompt.created"],
      status: "ACTIVE",
      description: "Desc 1",
      creation_timestamp: 0,
      last_updated_timestamp: 0,
    },
    {
      webhook_id: "2",
      name: "Webhook 2",
      url: "http://example.com/2",
      events: ["model_version.created"],
      status: "ACTIVE",
      creation_timestamp: 0,
      last_updated_timestamp: 0,
    },
  ];

  const mockShowToast = vi.fn();
  const mockRefresh = vi.fn();
  const mockUpdateLocalWebhook = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useWebhooksModule, "useWebhooks").mockReturnValue({
      webhooks: mockWebhooks,
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      updateLocalWebhook: mockUpdateLocalWebhook,
    } as unknown as ReturnType<typeof useWebhooksModule.useWebhooks>);

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
    } as unknown as ReturnType<typeof useToastModule.useToast>);
  });

  it("renders the page title, webhooks table, and add button", () => {
    render(<WebhooksPage />);
    expect(screen.getByText("Webhooks")).toBeInTheDocument();
    expect(screen.getByText("Webhook 1")).toBeInTheDocument();
    expect(screen.getByText("Webhook 2")).toBeInTheDocument();
    expect(screen.getByText("Desc 1")).toBeInTheDocument();
    expect(screen.getByText("-")).toBeInTheDocument(); // For Webhook 2 description
    expect(screen.getByText("http://example.com/1")).toBeInTheDocument();
    expect(screen.getByText("Add Webhook")).toBeInTheDocument();
  });

  it("opens CreateWebhookModal when Add webhook is clicked", () => {
    render(<WebhooksPage />);
    fireEvent.click(screen.getByText("Add Webhook"));
    expect(screen.getByText("Create webhook")).toBeInTheDocument();
  });

  it("opens EditWebhookModal when Edit button is clicked", async () => {
    render(<WebhooksPage />);
    const editButtons = screen.getAllByTitle("Edit");
    fireEvent.click(editButtons[0]);
    expect(await screen.findByText("Edit Webhook")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Webhook 1")).toBeInTheDocument();
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
        "success",
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
        'Webhook "Webhook 1" deleted successfully',
        "success",
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
