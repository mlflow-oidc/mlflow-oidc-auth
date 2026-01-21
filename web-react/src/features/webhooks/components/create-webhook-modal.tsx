import React, { useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { useToast } from "../../../shared/components/toast/use-toast";
import { createWebhook } from "../../../core/services/webhook-service";
import { WebhookForm } from "./webhook-form";
import type { WebhookCreateRequest } from "../../../shared/types/entity";

interface CreateWebhookModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const CreateWebhookModal: React.FC<CreateWebhookModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { showToast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (formData: WebhookCreateRequest) => {
    setIsSubmitting(true);
    try {
      const trimmedData = {
        ...formData,
        name: formData.name.trim(),
        url: formData.url.trim(),
        secret: (formData.secret || "").trim(),
      };
      await createWebhook(trimmedData);
      showToast("Webhook created successfully", "success");
      onSuccess();
      onClose();
    } catch (err) {
      console.error("Failed to create webhook:", err);
      showToast("Failed to create webhook", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create webhook">
      <WebhookForm
        onSubmit={handleSubmit}
        onCancel={onClose}
        submitLabel="Create"
        isSubmitting={isSubmitting}
      />
    </Modal>
  );
};
