import React, { useState } from "react";
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
  const [prevStatus, setPrevStatus] = useState(webhook.status);

  // Derive state adjustment pattern
  if (webhook.status !== prevStatus) {
    setPrevStatus(webhook.status);
    setIsActive(webhook.status === "ACTIVE");
  }

  const handleToggle = async () => {
    const newStatus = isActive ? "DISABLED" : "ACTIVE";
    const success = await update(
      webhook.webhook_id,
      { status: newStatus },
      {
        onSuccessMessage: `Webhook ${newStatus === "ACTIVE" ? "enabled" : "disabled"} successfully`,
        onErrorMessage: `Failed to update webhook status`,
      },
    );

    if (success) {
      setIsActive(!isActive);
      onSuccess?.(newStatus);
    }
  };

  return (
    <Switch
      checked={isActive}
      onChange={() => {
        void handleToggle();
      }}
      aria-label={`${isActive ? "Disable" : "Enable"} webhook`}
      disabled={isUpdating}
    />
  );
};
