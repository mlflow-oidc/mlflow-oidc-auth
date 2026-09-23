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

/** Today's date as `YYYY-MM-DD` in the viewer's local timezone (not UTC). */
function localDateString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/**
 * The end of the picked calendar day (23:59:59.999) in the viewer's local timezone, as an ISO
 * string.
 *
 * The `<input type="date">` value is a bare `YYYY-MM-DD` with no timezone. `new Date("YYYY-MM-DD")`
 * parses that as UTC midnight, which is a past instant (and so an already-expired token) for
 * anyone west of UTC picking "today". Building the Date from its local-time constructor instead
 * anchors the string to the viewer's own midnight, and pushing it to the end of that day means an
 * expiry of "today" still allows use through the rest of today wherever the viewer is.
 */
function endOfLocalDayIso(dateString: string): string {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(year, month - 1, day, 23, 59, 59, 999).toISOString();
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
        expires_at: expiresAt ? endOfLocalDayIso(expiresAt) : undefined,
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
          min={localDateString(new Date())}
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
