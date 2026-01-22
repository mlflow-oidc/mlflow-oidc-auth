import React, { useState, useEffect } from "react";
import { Modal } from "../../../shared/components/modal";
import { useUpdateWebhook } from "../../../core/hooks/use-update-webhook";
import { WebhookForm } from "./webhook-form";
import type { Webhook, WebhookUpdateRequest, WebhookCreateRequest } from "../../../shared/types/entity";

interface EditWebhookModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  webhook: Webhook | null;
}

export const EditWebhookModal: React.FC<EditWebhookModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  webhook,
}) => {
  const { update, isUpdating } = useUpdateWebhook();
  const [initialFormData, setInitialFormData] = useState<WebhookCreateRequest | undefined>();

  useEffect(() => {
    if (isOpen && webhook) {
      setInitialFormData({
        name: webhook.name,
        url: webhook.url,
        events: [...webhook.events],
        secret: "", // Secret is optional and not returned by API usually
      });
    }
  }, [isOpen, webhook]);

  const handleSubmit = async (formData: WebhookCreateRequest) => {
    if (!webhook) return;

    const updateData: WebhookUpdateRequest = {
      name: formData.name?.trim(),
      url: formData.url?.trim(),
      events: formData.events,
    };

    if (formData.secret?.trim()) {
      updateData.secret = formData.secret.trim();
    }

    const success = await update(
      webhook.webhook_id,
      updateData,
      {
        onSuccessMessage: `${webhook.name} webhook updated successfully`,
        onErrorMessage: `Failed to update ${webhook.name} webhook`,
      }
    );

    if (success) {
      onSuccess();
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit webhook">
      {initialFormData && (
        <WebhookForm
          initialData={initialFormData}
          onSubmit={handleSubmit}
          onCancel={onClose}
          submitLabel="Update"
          isSubmitting={isUpdating}
          isEdit
        />
      )}
    </Modal>
  );
};
