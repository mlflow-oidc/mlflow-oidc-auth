import React, { useState, useEffect } from "react";
import { Modal } from "../../../shared/components/modal";
import { Input } from "../../../shared/components/input";
import { Button } from "../../../shared/components/button";
import { useToast } from "../../../shared/components/toast/use-toast";
import { updateWebhook } from "../../../core/services/webhook-service";
import type { Webhook, WebhookUpdateRequest } from "../../../shared/types/entity";

interface EditWebhookModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  webhook: Webhook | null;
}

const SUPPORTED_EVENTS = [
  { group: "Model Registry", events: [
    "registered_model.created",
    "model_version.created",
    "model_version_tag.set",
    "model_version_tag.deleted",
    "model_version_alias.created",
    "model_version_alias.deleted",
  ]},
  { group: "Prompt Registry", events: [
    "prompt.created",
    "prompt_version.created",
    "prompt_tag.set",
    "prompt_tag.deleted",
    "prompt_version_tag.set",
    "prompt_version_tag.deleted",
    "prompt_alias.created",
    "prompt_alias.deleted",
  ]}
];

export const EditWebhookModal: React.FC<EditWebhookModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  webhook,
}) => {
  const { showToast } = useToast();
  const [formData, setFormData] = useState<WebhookUpdateRequest>({
    name: "",
    url: "",
    events: [],
    secret: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen && webhook) {
      setFormData({
        name: webhook.name,
        url: webhook.url,
        events: [...webhook.events],
        secret: "",
      });
      setErrors({});
    }
  }, [isOpen, webhook]);

  const validateURL = (url: string) => {
    try {
      const trimmedUrl = url.trim();
      const parsedUrl = new URL(trimmedUrl);
      return parsedUrl.protocol === "http:" || parsedUrl.protocol === "https:";
    } catch {
      return false;
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    if (!formData.name?.trim()) newErrors.name = "Name is required";
    if (!formData.url?.trim()) {
      newErrors.url = "URL is required";
    } else if (!validateURL(formData.url)) {
      newErrors.url = "Invalid URL format";
    }
    if (!formData.events || formData.events.length === 0) {
      newErrors.events = "At least one event must be selected";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleEventToggle = (event: string) => {
    setFormData((prev) => ({
      ...prev,
      events: prev.events?.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...(prev.events || []), event],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!webhook || !validateForm()) return;

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
      <form onSubmit={handleSubmit} aria-label="Edit webhook form">
        <Input
          label="Name"
          id="webhook-name"
          value={formData.name || ""}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          error={errors.name}
          required
          reserveErrorSpace
          containerClassName="mb-4"
        />

        <Input
          label="URL"
          id="webhook-url"
          value={formData.url || ""}
          onChange={(e) => setFormData({ ...formData, url: e.target.value })}
          error={errors.url}
          placeholder="https://example.com/webhook"
          required
          reserveErrorSpace
          containerClassName="mb-4"
        />

        <div className="mb-4">
          <label className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            Events*
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border border-ui-border dark:border-ui-border-dark rounded-md p-4 max-h-60 overflow-y-auto">
            {SUPPORTED_EVENTS.map((group) => (
              <div key={group.group} className="space-y-2">
                <h5 className="text-xs font-bold uppercase text-ui-text-muted dark:text-ui-text-muted-dark tracking-wider">
                  {group.group}
                </h5>
                {group.events.map((event) => (
                  <label key={event} className="flex items-center space-x-2 cursor-pointer group">
                    <input
                      id={`event-${event}`}
                      type="checkbox"
                      className="custom-checkbox w-4 h-4 rounded border-ui-border dark:border-ui-border-dark text-btn-primary focus:ring-btn-primary"
                      checked={formData.events?.includes(event) || false}
                      onChange={() => handleEventToggle(event)}
                    />
                    <span className="text-sm text-ui-text dark:text-ui-text-dark group-hover:text-btn-primary transition-colors">
                      {event}
                    </span>
                  </label>
                ))}
              </div>
            ))}
          </div>
          <p className={`mt-1 text-sm ${errors.events ? "text-red-500" : "invisible"}`}>
            {errors.events || "\u00A0"}
          </p>
        </div>

        <Input
          label="Secret (Optional)"
          id="webhook-secret"
          value={formData.secret || ""}
          onChange={(e) => setFormData({ ...formData, secret: e.target.value })}
          placeholder="Leave empty to keep current secret"
          reserveErrorSpace
          containerClassName="mb-4"
        />

        <div className="flex justify-end space-x-3 pt-2">
          <Button type="button" onClick={onClose} variant="ghost" disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            {isSubmitting ? "Updating..." : "Update"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
