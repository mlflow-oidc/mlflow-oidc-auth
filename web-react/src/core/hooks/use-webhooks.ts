import { useState, useEffect, useCallback } from "react";
import { listWebhooks } from "../services/webhook-service";
import type { Webhook, WebhookStatus } from "../../shared/types/entity";

export function useWebhooks() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchWebhooks = useCallback(async (isBackground = false) => {
    if (!isBackground) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const response = await listWebhooks();
      setWebhooks(response.webhooks);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      if (!isBackground) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void fetchWebhooks();
  }, [fetchWebhooks]);

  const refresh = useCallback(() => {
    void fetchWebhooks(true);
  }, [fetchWebhooks]);

  const updateLocalWebhook = useCallback(
    (id: string, status: WebhookStatus) => {
      setWebhooks((prev) =>
        prev.map((w) => (w.webhook_id === id ? { ...w, status } : w)),
      );
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
