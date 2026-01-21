import React, { useState, useEffect } from "react";
import { Modal } from "../../../shared/components/modal";
import { useToast } from "../../../shared/components/toast/use-toast";
import { updateWebhook } from "../../../core/services/webhook-service";
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
  const { showToast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [initialFormData, setInitialFormData] = useState<WebhookCreateRequest | undefined>();

  useEffect(() => {
    if (isOpen && webhook) {
      setInitialFormData({
        name: webhook.name,
        url: webhook.url,
        events: [...webhook.events],
        secret: "",
      });
    }
  }, [isOpen, webhook]);

  const handleSubmit = async (formData: WebhookCreateRequest) => {
    if (!webhook) return;

    setIsSubmitting(true);
    try {
      const updateData: WebhookUpdateRequest = {
        name: formData.name?.trim(),
        url: formData.url?.trim(),
        events: formData.events,
      };

      if (formData.secret?.trim()) {
        updateData.secret = formData.secret.trim();
      }

      await updateWebhook(webhook.webhook_id, updateData);
      showToast(`${webhook.name} webhook updated successfully`, "success");
      onSuccess();
      onClose();
    } catch (error) {
      console.error("Error updating webhook:", error);
      showToast(`Failed to update ${webhook.name} webhook`, "error");
    } finally {
      setIsSubmitting(false);
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
          isSubmitting={isSubmitting}
          isEdit
        />
      )}
    </Modal>
  );
};
