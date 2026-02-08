import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  listWebhooks,
  createWebhook,
  getWebhook,
  updateWebhook,
  deleteWebhook,
  testWebhook,
} from "./webhook-service";
import * as apiUtils from "./api-utils";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";

vi.mock("./api-utils", () => ({
  request: vi.fn(),
}));

describe("webhook-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("listWebhooks calls request with correct url", async () => {
    await listWebhooks();
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.WEBHOOKS_RESOURCE,
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("listWebhooks works without params", async () => {
    await listWebhooks();
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.WEBHOOKS_RESOURCE,
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("createWebhook calls request with POST and body", async () => {
    const data = {
      name: "test-webhook",
      url: "http://example.com/hook",
      events: ["experiment_created"],
    };
    await createWebhook(data);
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.WEBHOOKS_RESOURCE,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(data),
      }),
    );
  });

  it("getWebhook calls correct dynamic endpoint", async () => {
    const webhookId = "hook-123";
    await getWebhook(webhookId);
    expect(apiUtils.request).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}`),
      expect.objectContaining({}),
    );
  });

  it("updateWebhook calls request with PUT and body", async () => {
    const webhookId = "hook-123";
    const data = { status: "DISABLED" as const };
    await updateWebhook(webhookId, data);
    expect(apiUtils.request).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}`),
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify(data),
      }),
    );
  });

  it("deleteWebhook calls request with DELETE", async () => {
    const webhookId = "hook-123";
    await deleteWebhook(webhookId);
    expect(apiUtils.request).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}`),
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });

  it("testWebhook calls request with POST and optional body", async () => {
    const webhookId = "hook-123";
    const testData = { event: "ping" };
    await testWebhook(webhookId, testData);
    expect(apiUtils.request).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}/test`),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(testData),
      }),
    );
  });

  it("testWebhook works without optional body", async () => {
    const webhookId = "hook-123";
    await testWebhook(webhookId);
    expect(apiUtils.request).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}/test`),
      expect.objectContaining({
        method: "POST",
        body: undefined,
      }),
    );
  });

  it("calls request with webhook endpoint", async () => {
    await createWebhook({
      name: "test",
      url: "http://example.com",
      events: [],
    });
    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.WEBHOOKS_RESOURCE,
      expect.objectContaining({
        method: "POST",
      }),
    );
  });
});
