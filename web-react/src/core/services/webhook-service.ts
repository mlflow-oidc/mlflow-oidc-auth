import { http } from "./http";
import { resolveUrl } from "./api-utils";
import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
} from "../configs/api-endpoints";
import { createStaticApiFetcher } from "./create-api-fetcher";
import type {
  Webhook,
  WebhookCreateRequest,
  WebhookUpdateRequest,
  WebhookTestRequest,
  WebhookTestResponse,
} from "../../shared/types/entity";

export type WebhookListResponse = {
  webhooks: Webhook[];
  next_page_token?: string;
};

export const listWebhooks = createStaticApiFetcher<WebhookListResponse>({
  endpointKey: "WEBHOOKS_RESOURCE",
});

export const createWebhook = async (data: WebhookCreateRequest) => {
  const url = await resolveUrl(STATIC_API_ENDPOINTS.WEBHOOKS_RESOURCE, {});
  return http<Webhook>(url, {
    method: "POST",
    body: JSON.stringify(data),
  });
};

export const getWebhook = async (webhookId: string) => {
  const url = await resolveUrl(
    DYNAMIC_API_ENDPOINTS.WEBHOOK_DETAILS(webhookId),
    {},
  );
  return http<Webhook>(url);
};

export const updateWebhook = async (
  webhookId: string,
  data: WebhookUpdateRequest,
) => {
  const url = await resolveUrl(
    DYNAMIC_API_ENDPOINTS.WEBHOOK_DETAILS(webhookId),
    {},
  );
  return http<Webhook>(url, {
    method: "PUT",
    body: JSON.stringify(data),
  });
};

export const deleteWebhook = async (webhookId: string) => {
  const url = await resolveUrl(
    DYNAMIC_API_ENDPOINTS.WEBHOOK_DETAILS(webhookId),
    {},
  );
  return http<{ message: string }>(url, {
    method: "DELETE",
  });
};

export const testWebhook = async (
  webhookId: string,
  data?: WebhookTestRequest,
) => {
  const url = await resolveUrl(
    DYNAMIC_API_ENDPOINTS.TEST_WEBHOOK(webhookId),
    {},
  );
  return http<WebhookTestResponse>(url, {
    method: "POST",
    body: data ? JSON.stringify(data) : undefined,
  });
};
