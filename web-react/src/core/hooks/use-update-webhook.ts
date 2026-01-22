import { useState } from "react";
import { updateWebhook } from "../services/webhook-service";
import { useToast } from "../../shared/components/toast/use-toast";
import type { WebhookUpdateRequest } from "../../shared/types/entity";

interface UpdateOptions {
  onSuccessMessage: string;
  onErrorMessage: string;
}

export function useUpdateWebhook() {
  const [isUpdating, setIsUpdating] = useState(false);
  const { showToast } = useToast();

  const update = async (
    id: string,
    data: WebhookUpdateRequest,
    options: UpdateOptions
  ) => {
    setIsUpdating(true);
    try {
      await updateWebhook(id, data);
      showToast(options.onSuccessMessage, "success");
      return true;
    } catch (err) {
      console.error(options.onErrorMessage, err);
      showToast(options.onErrorMessage, "error");
      return false;
    } finally {
      setIsUpdating(false);
    }
  };

  return { update, isUpdating };
}
