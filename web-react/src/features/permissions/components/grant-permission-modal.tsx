import React, { useState } from "react";
import { Button } from "../../../shared/components/button";
import { Modal } from "../../../shared/components/modal";
import { Select } from "../../../shared/components/select";
import type { PermissionLevel } from "../../../shared/types/entity";

interface GrantPermissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (identifier: string, permission: PermissionLevel) => Promise<void>;
  title: string;
  label: string;
  options: (string | { label: string; value: string })[];
  isLoading?: boolean;
}

const PERMISSION_LEVELS: PermissionLevel[] = [
  "READ",
  "EDIT",
  "MANAGE",
  "NO_PERMISSIONS",
];

export const GrantPermissionModal: React.FC<GrantPermissionModalProps> = ({
  isOpen,
  onClose,
  onSave,
  title,
  label,
  options,
  isLoading = false,
}) => {
  const [selectedUsername, setSelectedUsername] = useState<string>("");
  const [selectedPermission, setSelectedPermission] =
    useState<PermissionLevel>("READ");

  // State reset is handled by 'key' prop in parent

  const handleSave = async () => {
    if (!selectedUsername) return;
    await onSave(selectedUsername, selectedPermission);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <Select
        id="username-select"
        label={label}
        value={selectedUsername}
        onChange={(e) => setSelectedUsername(e.target.value)}
        required
        options={[
          { label: `Select ${label.toLowerCase()}...`, value: "" },
          ...options,
        ].map((opt) =>
          typeof opt === "string" ? { label: opt, value: opt } : opt,
        )}
        containerClassName="mb-4"
      />

      <Select
        id="permission-level"
        label="Permissions"
        value={selectedPermission}
        onChange={(e) =>
          setSelectedPermission(e.target.value as PermissionLevel)
        }
        required
        options={PERMISSION_LEVELS.map((level) => ({
          label: level,
          value: level,
        }))}
        containerClassName="mb-4"
      />

      <div className="flex justify-end space-x-3">
        <Button onClick={onClose} variant="ghost" disabled={isLoading}>
          Cancel
        </Button>
        <Button
          onClick={() => {
            void handleSave();
          }}
          variant="primary"
          disabled={isLoading || !selectedUsername}
        >
          {isLoading ? "Saving..." : "Save"}
        </Button>
      </div>
    </Modal>
  );
};
