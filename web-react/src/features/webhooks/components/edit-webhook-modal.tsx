import React, { useMemo } from "react";
import { Modal } from "../../../shared/components/modal";
import { useUpdateWebhook } from "../../../core/hooks/use-update-webhook";
import { WebhookForm } from "./webhook-form";
import type {
  Webhook,
  WebhookUpdateRequest,
  WebhookCreateRequest,
} from "../../../shared/types/entity";

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

  const initialFormData = useMemo(() => {
    if (!webhook) return undefined;
    return {
      name: webhook.name,
      description: webhook.description || "",
      url: webhook.url,
      events: [...webhook.events],
      secret: "", // Secret is optional and not returned by API
    };
  }, [webhook]);

  const handleSubmit = async (formData: WebhookCreateRequest) => {
    if (!webhook) return;

    const updateData: WebhookUpdateRequest = {
      name: formData.name?.trim(),
      description: formData.description?.trim(),
      url: formData.url?.trim(),
      events: formData.events,
    };

    if (formData.secret?.trim()) {
      updateData.secret = formData.secret.trim();
    }

    const success = await update(webhook.webhook_id, updateData, {
      onSuccessMessage: `Webhook ${webhook.name} updated successfully`,
      onErrorMessage: `Failed to update Webhook ${webhook.name}`,
    });

    if (success) {
      onSuccess();
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit Webhook">
      {initialFormData && (
        <WebhookForm
          key={webhook?.webhook_id}
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
