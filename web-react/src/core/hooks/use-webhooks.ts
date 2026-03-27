import { useState, useCallback } from "react";
import {
  listWebhooks,
  type WebhookListResponse,
} from "../services/webhook-service";
import type { Webhook, WebhookStatus } from "../../shared/types/entity";
import { useApi } from "./use-api";

export function useWebhooks() {
  const {
    data: response,
    isLoading,
    error,
    refetch,
  } = useApi<WebhookListResponse>(listWebhooks);

  const [localOverrides, setLocalOverrides] = useState<
    Map<string, Partial<Webhook>>
  >(new Map());

  const webhooks = (response?.webhooks ?? []).map((w) => {
    const overrides = localOverrides.get(w.webhook_id);
    return overrides ? { ...w, ...overrides } : w;
  });

  const refresh = useCallback(() => {
    setLocalOverrides(new Map());
    refetch();
  }, [refetch]);

  const updateLocalWebhook = useCallback(
    (id: string, status: WebhookStatus) => {
      setLocalOverrides((prev) => new Map(prev).set(id, { status }));
    },
    [],
  );

  return {
    webhooks,
    isLoading,
    error,
    refresh,
    updateLocalWebhook,
  };
}
