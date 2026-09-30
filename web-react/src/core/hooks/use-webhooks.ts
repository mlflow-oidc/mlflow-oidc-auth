import { useState, useCallback, useMemo } from "react";
import { fetchWebhooksPage } from "../services/webhook-service";
import type { Webhook, WebhookStatus } from "../../shared/types/entity";
import { usePagedList } from "./use-paged-list";

/**
 * One page of webhooks, searched server-side on the webhook name.
 *
 * `updateLocalWebhook` applies an optimistic status change without a refetch; `refresh` clears
 * those overrides and refetches the current page.
 *
 * @param search - Submitted search term; changing it goes back to page 1.
 */
export function useWebhooks(search = "") {
  const {
    items,
    total,
    pagination,
    isLoading,
    error,
    refresh: refetch,
  } = usePagedList(fetchWebhooksPage, search);

  const [localOverrides, setLocalOverrides] = useState<
    Map<string, Partial<Webhook>>
  >(() => new Map());

  const webhooks = useMemo(
    () =>
      items.map((w) => {
        const overrides = localOverrides.get(w.webhook_id);
        return overrides ? { ...w, ...overrides } : w;
      }),
    [items, localOverrides],
  );

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
    total,
    pagination,
    isLoading,
    error,
    refresh,
    updateLocalWebhook,
  };
}
