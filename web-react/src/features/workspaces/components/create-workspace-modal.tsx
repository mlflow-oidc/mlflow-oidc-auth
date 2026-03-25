import React, { useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Input } from "../../../shared/components/input";
import { Button } from "../../../shared/components/button";
import { useToast } from "../../../shared/components/toast/use-toast";
import { createWorkspace } from "../../../core/services/workspace-service";

interface CreateWorkspaceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const DNS_SAFE_PATTERN = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;
const RESERVED_NAMES = ["default"];

export function validateWorkspaceName(name: string): string | null {
  if (!name) return "Workspace name is required";
  if (name.length < 2) return "Name must be at least 2 characters";
  if (name.length > 63) return "Name must be at most 63 characters";
  if (!DNS_SAFE_PATTERN.test(name))
    return "Name must be DNS-safe: lowercase letters, digits, hyphens; must start and end with alphanumeric";
  if (RESERVED_NAMES.includes(name)) return "This name is reserved";
  return null;
}

export const CreateWorkspaceModal: React.FC<CreateWorkspaceModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { showToast } = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [artifactRoot, setArtifactRoot] = useState("");
  const [nameError, setNameError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setName(value);
    const error = validateWorkspaceName(value);
    setNameError(error || "");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    const trimmedDescription = description.trim();
    const trimmedArtifactRoot = artifactRoot.trim();

    const error = validateWorkspaceName(trimmedName);
    if (error) {
      setNameError(error);
      return;
    }

    setIsSubmitting(true);
    try {
      await createWorkspace({
        name: trimmedName,
        description: trimmedDescription || undefined,
        default_artifact_root: trimmedArtifactRoot || undefined,
      });
      showToast("Workspace created successfully", "success");
      onSuccess();
      onClose();
    } catch (err) {
      console.error("Failed to create workspace:", err);
      showToast("Failed to create workspace", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Workspace">
      <div key={isOpen ? "open" : "closed"}>
        <form onSubmit={handleSubmit} role="form">
          <Input
            id="workspace-name"
            label="Name"
            required
            value={name}
            onChange={handleNameChange}
            error={nameError}
            reserveErrorSpace={true}
            placeholder="my-workspace"
          />
          <Input
            id="workspace-description"
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            containerClassName="mt-2"
          />
          <Input
            id="workspace-artifact-root"
            label="Default Artifact Root"
            value={artifactRoot}
            onChange={(e) => setArtifactRoot(e.target.value)}
            placeholder="e.g. s3://team-artifacts"
            containerClassName="mt-2"
          />
          <div className="flex justify-end space-x-3 mt-6">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={isSubmitting || !name.trim() || !!nameError}
            >
              {isSubmitting ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
};
