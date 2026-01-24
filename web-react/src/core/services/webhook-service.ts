import { http } from "./http";
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
  return http<Webhook>(STATIC_API_ENDPOINTS.WEBHOOKS_RESOURCE, {
    method: "POST",
    body: JSON.stringify(data),
  });
};

export const getWebhook = async (webhookId: string) => {
  return http<Webhook>(DYNAMIC_API_ENDPOINTS.WEBHOOK_DETAILS(webhookId));
};

export const updateWebhook = async (
  webhookId: string,
  data: WebhookUpdateRequest,
) => {
  return http<Webhook>(DYNAMIC_API_ENDPOINTS.WEBHOOK_DETAILS(webhookId), {
    method: "PUT",
    body: JSON.stringify(data),
  });
};

export const deleteWebhook = async (webhookId: string) => {
  return http<{ message: string }>(
    DYNAMIC_API_ENDPOINTS.WEBHOOK_DETAILS(webhookId),
    {
      method: "DELETE",
    },
  );
};

export const testWebhook = async (
  webhookId: string,
  data?: WebhookTestRequest,
) => {
  return http<WebhookTestResponse>(
    DYNAMIC_API_ENDPOINTS.TEST_WEBHOOK(webhookId),
    {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    },
  );
};
