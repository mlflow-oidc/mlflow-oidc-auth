import React, { useState, useEffect } from "react";
import { Modal } from "../../../shared/components/modal";
import { Input } from "../../../shared/components/input";
import { Button } from "../../../shared/components/button";
import { useToast } from "../../../shared/components/toast/use-toast";
import { createWebhook } from "../../../core/services/webhook-service";
import type { WebhookCreateRequest } from "../../../shared/types/entity";

interface CreateWebhookModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
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

export const CreateWebhookModal: React.FC<CreateWebhookModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { showToast } = useToast();
  const [formData, setFormData] = useState<WebhookCreateRequest>({
    name: "",
    url: "",
    events: [],
    secret: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: "",
        url: "",
        events: [],
        secret: "",
      });
      setErrors({});
    }
  }, [isOpen]);

  const validateURL = (url: string) => {
    try {
      new URL(url.trim());
      return true;
    } catch {
      return false;
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) newErrors.name = "Name is required";
    if (!formData.url.trim()) {
      newErrors.url = "URL is required";
    } else if (!validateURL(formData.url)) {
      newErrors.url = "Invalid URL format";
    }
    if (formData.events.length === 0) newErrors.events = "At least one event must be selected";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleEventToggle = (event: string) => {
    setFormData((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

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
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Name"
          id="webhook-name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          error={errors.name}
          required
          reserveErrorSpace
        />

        <Input
          label="URL"
          id="webhook-url"
          value={formData.url}
          onChange={(e) => setFormData({ ...formData, url: e.target.value })}
          error={errors.url}
          placeholder="https://example.com/webhook"
          required
          reserveErrorSpace
        />

        <div className="space-y-2">
          <label className="block text-sm font-medium text-text-primary dark:text-text-primary-dark">
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
                      type="checkbox"
                      className="custom-checkbox w-4 h-4 rounded border-ui-border dark:border-ui-border-dark text-btn-primary focus:ring-btn-primary"
                      checked={formData.events.includes(event)}
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
          {errors.events && (
            <p className="text-sm text-red-500">{errors.events}</p>
          )}
        </div>

        <Input
          label="Secret (Optional)"
          id="webhook-secret"
          value={formData.secret}
          onChange={(e) => setFormData({ ...formData, secret: e.target.value })}
          placeholder="Webhook secret for HMAC verification"
          reserveErrorSpace
        />

        <div className="flex justify-end space-x-3 pt-2">
          <Button type="button" onClick={onClose} variant="ghost" disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            {isSubmitting ? "Creating..." : "Create"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
