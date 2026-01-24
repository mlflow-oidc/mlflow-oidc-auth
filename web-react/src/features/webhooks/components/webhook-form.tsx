import React, { useState, useEffect } from "react";
import { Input } from "../../../shared/components/input";
import { Button } from "../../../shared/components/button";
import type { WebhookCreateRequest } from "../../../shared/types/entity";

export const SUPPORTED_EVENTS = [
  {
    group: "Model Registry",
    events: [
      "registered_model.created",
      "model_version.created",
      "model_version_tag.set",
      "model_version_tag.deleted",
      "model_version_alias.created",
      "model_version_alias.deleted",
    ],
  },
  {
    group: "Prompt Registry",
    events: [
      "prompt.created",
      "prompt_version.created",
      "prompt_tag.set",
      "prompt_tag.deleted",
      "prompt_version_tag.set",
      "prompt_version_tag.deleted",
      "prompt_alias.created",
      "prompt_alias.deleted",
    ],
  },
];

interface WebhookFormProps {
  initialData?: WebhookCreateRequest;
  onSubmit: (data: WebhookCreateRequest) => Promise<void>;
  onCancel: () => void;
  submitLabel: string;
  isSubmitting: boolean;
  isEdit?: boolean;
}

export const WebhookForm: React.FC<WebhookFormProps> = ({
  initialData,
  onSubmit,
  onCancel,
  submitLabel,
  isSubmitting,
  isEdit = false,
}) => {
  const [formData, setFormData] = useState<WebhookCreateRequest>(
    initialData || {
      name: "",
      url: "",
      events: [],
      secret: "",
    },
  );
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (initialData) {
      setFormData(initialData);
    }
  }, [initialData]);

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
    if (formData.description && formData.description.length > 500) {
      newErrors.description = "Description must be 500 characters or less";
    }
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      onSubmit(formData);
    }
  };

  const editingLabel = isEdit ? "Updating..." : "Creating...";

  return (
    <form
      onSubmit={handleSubmit}
      aria-label={isEdit ? "Edit webhook form" : "Create webhook form"}
    >
      <Input
        label="Name"
        id="webhook-name"
        value={formData.name || ""}
        onChange={(e) =>
          setFormData((prev) => ({ ...prev, name: e.target.value }))
        }
        error={errors.name}
        required
        reserveErrorSpace
        containerClassName="mb-2"
      />

      <div className="mb-2">
        <label
          htmlFor="webhook-description"
          className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1"
        >
          Description
        </label>
        <textarea
          id="webhook-description"
          value={formData.description || ""}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, description: e.target.value }))
          }
          className={`w-full rounded-md border text-sm p-2 bg-ui-bg dark:bg-ui-bg-dark text-text-primary dark:text-text-primary-dark focus:ring-2 focus:ring-btn-primary focus:border-transparent ${
            errors.description
              ? "border-red-500 focus:ring-red-500"
              : "border-ui-border dark:border-ui-border-dark"
          }`}
          rows={3}
          placeholder="Optional description (max 500 characters)"
        />
        <p
          className={`mt-1 text-sm ${errors.description ? "text-red-500" : "invisible"}`}
        >
          {errors.description || "\u00A0"}
        </p>
      </div>

      <Input
        label="URL"
        id="webhook-url"
        value={formData.url || ""}
        onChange={(e) =>
          setFormData((prev) => ({ ...prev, url: e.target.value }))
        }
        error={errors.url}
        placeholder="https://example.com/webhook"
        required
        reserveErrorSpace
        containerClassName="mb-2"
      />

      <div className="mb-2">
        <div className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
          Events*
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border border-ui-border dark:border-ui-border-dark rounded-md p-4 max-h-40 overflow-y-auto">
          {SUPPORTED_EVENTS.map((group) => (
            <div key={group.group} className="space-y-2">
              <h5 className="text-xs font-bold uppercase text-ui-text-muted dark:text-ui-text-muted-dark tracking-wider">
                {group.group}
              </h5>
              {group.events.map((event) => (
                <label
                  key={event}
                  className="flex items-center space-x-2 cursor-pointer group"
                >
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
        <p
          className={`mt-1 text-sm ${errors.events ? "text-red-500" : "invisible"}`}
        >
          {errors.events || "\u00A0"}
        </p>
      </div>

      <Input
        label="Secret (Optional)"
        id="webhook-secret"
        value={formData.secret || ""}
        onChange={(e) =>
          setFormData((prev) => ({ ...prev, secret: e.target.value }))
        }
        placeholder={
          isEdit
            ? "Leave empty to keep current secret"
            : "Webhook secret for HMAC verification"
        }
        reserveErrorSpace
        containerClassName="mb-2"
      />

      <div className="flex justify-end space-x-3 pt-2">
        <Button
          type="button"
          onClick={onCancel}
          variant="ghost"
          disabled={isSubmitting}
        >
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={isSubmitting}>
          {isSubmitting ? editingLabel : submitLabel}
        </Button>
      </div>
    </form>
  );
};
