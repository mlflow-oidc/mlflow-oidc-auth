import { listWebhooks } from "../services/webhook-service";
import { useApi } from "./use-api";
import type { WebhookListResponse } from "../services/webhook-service";

export function useWebhooks() {
  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<WebhookListResponse>(listWebhooks);

  return { 
    webhooks: data?.webhooks || [], 
    isLoading, 
    error, 
    refresh 
  };
}
