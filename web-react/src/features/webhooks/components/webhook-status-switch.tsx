import React, { useState, useEffect } from "react";
import { Switch } from "../../../shared/components/switch";
import { useUpdateWebhook } from "../../../core/hooks/use-update-webhook";
import type { Webhook, WebhookStatus } from "../../../shared/types/entity";

interface WebhookStatusSwitchProps {
  webhook: Webhook;
  onSuccess?: (newStatus: WebhookStatus) => void;
}

export const WebhookStatusSwitch: React.FC<WebhookStatusSwitchProps> = ({
  webhook,
  onSuccess,
}) => {
  const { update, isUpdating } = useUpdateWebhook();
  const [isActive, setIsActive] = useState(webhook.status === "ACTIVE");

  useEffect(() => {
    setIsActive(webhook.status === "ACTIVE");
  }, [webhook.status]);

  const handleToggle = async () => {
    const originalIsActive = isActive;
    const newStatus = originalIsActive ? "DISABLED" : "ACTIVE";
    setIsActive(!originalIsActive);

    const success = await update(
      webhook.webhook_id,
      { status: newStatus },
      {
        onSuccessMessage: `Webhook "${webhook.name}" ${
          newStatus === "ACTIVE" ? "activated" : "disabled"
        }`,
        onErrorMessage: "Failed to update webhook status",
      },
    );

    if (success) {
      onSuccess?.(newStatus);
    } else {
      setIsActive(originalIsActive);
    }
  };

  return (
    <Switch
      checked={isActive}
      onChange={handleToggle}
      className={`transition-colors duration-200 ${isUpdating ? "opacity-70" : ""}`}
      disabled={isUpdating}
    />
  );
};
