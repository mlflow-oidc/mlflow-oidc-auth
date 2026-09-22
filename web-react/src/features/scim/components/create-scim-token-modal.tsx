import React, { useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { Input } from "../../../shared/components/input";
import { useToast } from "../../../shared/components/toast/use-toast";
import { createScimToken } from "../services/scim-token-service";
import type { ScimTokenWithSecret } from "../../../shared/types/scim";

interface CreateScimTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (token: ScimTokenWithSecret) => void;
}

export const CreateScimTokenModal: React.FC<CreateScimTokenModalProps> = ({
  isOpen,
  onClose,
  onCreated,
}) => {
  const [name, setName] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { showToast } = useToast();

  const resetAndClose = () => {
    setName("");
    setExpiresAt("");
    onClose();
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      const token = await createScimToken({
        name: name.trim(),
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : undefined,
      });
      showToast(`Token "${token.name}" created`, "success");
      setName("");
      setExpiresAt("");
      onCreated(token);
    } catch (err) {
      console.error("Failed to create SCIM token:", err);
      showToast("Failed to create SCIM token", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={resetAndClose} title="Create SCIM token">
      <div className="space-y-4">
        <Input
          id="scim-token-name"
          label="Name*"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Entra ID provisioning"
          required
        />
        <Input
          id="scim-token-expires-at"
          label="Expires on"
          type="date"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
          min={new Date().toISOString().split("T")[0]}
        />
      </div>

      <div className="flex justify-end space-x-3 pt-4 border-t border-ui-secondary-bg dark:border-ui-secondary-bg-dark">
        <Button onClick={resetAndClose} variant="ghost" disabled={isSubmitting}>
          Cancel
        </Button>
        <Button
          onClick={() => {
            void handleSave();
          }}
          variant="primary"
          disabled={!name.trim() || isSubmitting}
        >
          {isSubmitting ? "Creating..." : "Create"}
        </Button>
      </div>
    </Modal>
  );
};
