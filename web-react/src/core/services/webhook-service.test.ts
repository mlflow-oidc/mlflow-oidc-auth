import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  listWebhooks,
  createWebhook,
  getWebhook,
  updateWebhook,
  deleteWebhook,
  testWebhook,
} from "./webhook-service";
import { http } from "./http";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";

vi.mock("./http");
vi.mock("../../shared/services/runtime-config", () => ({
  getRuntimeConfig: vi.fn().mockResolvedValue({ basePath: "" }),
}));

describe("webhook-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("listWebhooks calls http with correct url", async () => {
    await listWebhooks();
    expect(http).toHaveBeenCalledWith(
      expect.stringContaining(STATIC_API_ENDPOINTS.WEBHOOKS_RESOURCE),
      expect.any(Object)
    );
  });

  it("listWebhooks works without params", async () => {
    await listWebhooks();
    expect(http).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.WEBHOOKS_RESOURCE,
      expect.any(Object)
    );
  });

  it("createWebhook calls http with POST and body", async () => {
    const data = {
      name: "test-webhook",
      url: "http://example.com/hook",
      events: ["experiment_created"],
    };
    await createWebhook(data);
    expect(http).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.WEBHOOKS_RESOURCE,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(data),
      })
    );
  });

  it("getWebhook calls correct dynamic endpoint", async () => {
    const webhookId = "hook-123";
    await getWebhook(webhookId);
    expect(http).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}`)
    );
  });

  it("updateWebhook calls http with PUT and body", async () => {
    const webhookId = "hook-123";
    const data = { active: false };
    await updateWebhook(webhookId, data);
    expect(http).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}`),
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify(data),
      })
    );
  });

  it("deleteWebhook calls http with DELETE", async () => {
    const webhookId = "hook-123";
    await deleteWebhook(webhookId);
    expect(http).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}`),
      expect.objectContaining({
        method: "DELETE",
      })
    );
  });

  it("testWebhook calls http with POST and optional body", async () => {
    const webhookId = "hook-123";
    const testData = { event: "ping" };
    await testWebhook(webhookId, testData);
    expect(http).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}/test`),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(testData),
      })
    );
  });

  it("testWebhook works without optional body", async () => {
    const webhookId = "hook-123";
    await testWebhook(webhookId);
    expect(http).toHaveBeenCalledWith(
      expect.stringContaining(`/oidc/webhook/${webhookId}/test`),
      expect.objectContaining({
        method: "POST",
        body: undefined,
      })
    );
  });
});
