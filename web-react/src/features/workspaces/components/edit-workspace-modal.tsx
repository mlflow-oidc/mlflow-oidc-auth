import React, { useState, useEffect } from "react";
import { Modal } from "../../../shared/components/modal";
import { Input } from "../../../shared/components/input";
import { Button } from "../../../shared/components/button";
import { useToast } from "../../../shared/components/toast/use-toast";
import { updateWorkspace } from "../../../core/services/workspace-service";

interface EditWorkspaceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  workspace: { name: string; description: string } | null;
}

export const EditWorkspaceModal: React.FC<EditWorkspaceModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  workspace,
}) => {
  const { showToast } = useToast();
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (workspace) {
      setDescription(workspace.description);
    }
  }, [workspace]);

  if (!workspace) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await updateWorkspace(workspace.name, {
        description: description.trim(),
      });
      showToast("Workspace updated successfully", "success");
      onSuccess();
      onClose();
    } catch (err) {
      console.error("Failed to update workspace:", err);
      showToast("Failed to update workspace", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit Workspace">
      <form onSubmit={handleSubmit} role="form">
        <Input
          id="workspace-name"
          label="Name"
          value={workspace.name}
          readOnly
          disabled
        />
        <Input
          id="workspace-description"
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Enter description"
          containerClassName="mt-2"
        />
        <div className="flex justify-end space-x-3 mt-6">
          <Button variant="ghost" onClick={onClose}>
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
