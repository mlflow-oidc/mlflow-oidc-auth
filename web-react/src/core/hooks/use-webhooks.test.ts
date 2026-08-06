import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useWebhooks } from "./use-webhooks";
import * as webhookService from "../services/webhook-service";
import type { WebhookListResponse } from "../services/webhook-service";
import * as useAuthModule from "./use-auth";
import type { UseAuthResult } from "./use-auth";
import * as workspaceContext from "../../shared/context/use-workspace";

vi.mock("../services/webhook-service");
vi.mock("./use-auth");
vi.mock("../../shared/context/use-workspace");

describe("useWebhooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
    vi.spyOn(workspaceContext, "useSelectedWorkspace").mockReturnValue(
      "default",
    );
  });

  it("returns webhooks data", async () => {
    const mockWebhooks: WebhookListResponse = {
      webhooks: [
        {
          webhook_id: "1",
          name: "Webhook 1",
          url: "http://example.com/1",
          description: "Test webhook",
          events: ["REGISTERED_MODEL_CREATED"],
          status: "ACTIVE",
          creation_timestamp: 123456789,
          last_updated_timestamp: 123456789,
        },
      ],
    };
    vi.spyOn(webhookService, "listWebhooks").mockResolvedValue(mockWebhooks);

    const { result } = renderHook(() => useWebhooks());

    await waitFor(() => {
      expect(result.current.webhooks).toEqual(mockWebhooks.webhooks);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("returns empty array and error on failure", async () => {
    const mockError = new Error("Failed to fetch");
    vi.spyOn(webhookService, "listWebhooks").mockRejectedValue(mockError);

    const { result } = renderHook(() => useWebhooks());

    await waitFor(() => {
      expect(result.current.webhooks).toEqual([]);
      expect(result.current.error).toEqual(mockError);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("applies local status overrides from updateLocalWebhook", async () => {
    const mockWebhooks: WebhookListResponse = {
      webhooks: [
        {
          webhook_id: "1",
          name: "Webhook 1",
          url: "http://example.com/1",
          description: "Test webhook",
          events: ["REGISTERED_MODEL_CREATED"],
          status: "ACTIVE",
          creation_timestamp: 123456789,
          last_updated_timestamp: 123456789,
        },
      ],
    };
    vi.spyOn(webhookService, "listWebhooks").mockResolvedValue(mockWebhooks);

    const { result } = renderHook(() => useWebhooks());

    await waitFor(() => {
      expect(result.current.webhooks[0].status).toBe("ACTIVE");
    });

    act(() => {
      result.current.updateLocalWebhook("1", "DISABLED");
    });

    expect(result.current.webhooks[0].status).toBe("DISABLED");
  });

  it("refetches when workspace changes", async () => {
    const mockWebhooks: WebhookListResponse = {
      webhooks: [
        {
          webhook_id: "1",
          name: "Webhook 1",
          url: "http://example.com/1",
          description: "Test webhook",
          events: ["REGISTERED_MODEL_CREATED"],
          status: "ACTIVE",
          creation_timestamp: 123456789,
          last_updated_timestamp: 123456789,
        },
      ],
    };
    const listSpy = vi
      .spyOn(webhookService, "listWebhooks")
      .mockResolvedValue(mockWebhooks);
    const workspaceSpy = vi.spyOn(
      workspaceContext,
      "useSelectedWorkspace",
    );

    workspaceSpy.mockReturnValue("workspace-a");
    const { result, rerender } = renderHook(() => useWebhooks());

    await waitFor(() => {
      expect(result.current.webhooks).toHaveLength(1);
    });

    const callCountAfterFirstFetch = listSpy.mock.calls.length;

    // Change workspace
    workspaceSpy.mockReturnValue("workspace-b");
    rerender();

    await waitFor(() => {
      expect(listSpy.mock.calls.length).toBeGreaterThan(
        callCountAfterFirstFetch,
      );
    });
  });
});
