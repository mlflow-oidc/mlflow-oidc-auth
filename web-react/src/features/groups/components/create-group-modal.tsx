import React, { useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { Input } from "../../../shared/components/input";
import { useToast } from "../../../shared/components/toast/use-toast";
import { createGroup } from "../../../core/services/entity-service";
import { extractErrorMessage } from "../../../core/services/http";

interface CreateGroupModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

/**
 * Lets an admin create a group by typing its name, instead of waiting for one of its members to
 * sign in first (issues #64, #201, #63). The endpoint is idempotent, so submitting a name that
 * already exists is not an error — it just does not change anything (a directory-managed group
 * keeps its owner).
 */
export const CreateGroupModal: React.FC<CreateGroupModalProps> = ({
  isOpen,
  onClose,
  onCreated,
}) => {
  const [groupName, setGroupName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { showToast } = useToast();

  const resetAndClose = () => {
    setGroupName("");
    onClose();
  };

  const handleSave = async () => {
    const name = groupName.trim();
    if (!name) return;
    setIsSubmitting(true);
    try {
      const { status } = await createGroup(name);
      showToast(
        status === 201
          ? `Group "${name}" created`
          : `Group "${name}" already exists`,
        "success",
      );
      setGroupName("");
      onCreated();
    } catch (err) {
      console.error("Failed to create group:", err);
      showToast(extractErrorMessage(err, "Failed to create group"), "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={resetAndClose} title="Create group">
      <Input
        id="create-group-name"
        label="Group name*"
        type="text"
        value={groupName}
        onChange={(e) => setGroupName(e.target.value)}
        placeholder="data-team"
        required
        maxLength={255}
      />

      <div className="flex justify-end space-x-3 pt-4 border-t border-ui-secondary-bg dark:border-ui-secondary-bg-dark">
        <Button onClick={resetAndClose} variant="ghost" disabled={isSubmitting}>
          Cancel
        </Button>
        <Button
          onClick={() => {
            void handleSave();
          }}
          variant="primary"
          disabled={!groupName.trim() || isSubmitting}
        >
          {isSubmitting ? "Creating..." : "Create"}
        </Button>
      </div>
    </Modal>
  );
};
