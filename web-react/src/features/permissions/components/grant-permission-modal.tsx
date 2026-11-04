import React, { useId, useState } from "react";
import { Button } from "../../../shared/components/button";
import { Input } from "../../../shared/components/input";
import { Modal } from "../../../shared/components/modal";
import { Select } from "../../../shared/components/select";
import { PermissionLevelSelect } from "../../../shared/components/permission-level-select";
import type {
  PermissionLevel,
  PermissionType,
} from "../../../shared/types/entity";

interface GrantPermissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (identifier: string, permission: PermissionLevel) => Promise<void>;
  title: string;
  label: string;
  options: (string | { label: string; value: string })[];
  type: PermissionType;
  isLoading?: boolean;
  /**
   * Accept a typed name, with `options` as suggestions only. Needed when the server
   * restricts user and group listing, so the options may not include the grantee.
   */
  allowCustomValue?: boolean;
}

export const GrantPermissionModal: React.FC<GrantPermissionModalProps> = ({
  isOpen,
  onClose,
  onSave,
  title,
  label,
  options,
  type,
  isLoading = false,
  allowCustomValue = false,
}) => {
  const [selectedUsername, setSelectedUsername] = useState<string>("");
  const [selectedPermission, setSelectedPermission] =
    useState<PermissionLevel>("READ");

  // State reset is handled by 'key' prop in parent

  const suggestionsId = useId();
  const identifier = selectedUsername.trim();
  const normalizedOptions = options.map((opt) =>
    typeof opt === "string" ? { label: opt, value: opt } : opt,
  );

  const handleSave = async () => {
    if (!identifier) return;
    await onSave(identifier, selectedPermission);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      {allowCustomValue ? (
        <Input
          id="username-select"
          label={label}
          value={selectedUsername}
          onChange={(e) => setSelectedUsername(e.target.value)}
          placeholder={`Enter ${label.toLowerCase()}...`}
          list={suggestionsId}
          autoComplete="off"
          required
          containerClassName="mb-4"
        >
          <datalist id={suggestionsId}>
            {normalizedOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </datalist>
        </Input>
      ) : (
        <Select
          id="username-select"
          label={label}
          value={selectedUsername}
          onChange={(e) => setSelectedUsername(e.target.value)}
          required
          options={[
            { label: `Select ${label.toLowerCase()}...`, value: "" },
            ...normalizedOptions,
          ]}
          containerClassName="mb-4"
        />
      )}

      <PermissionLevelSelect
        id="permission-level"
        label="Permissions"
        value={selectedPermission}
        onChange={(val) => setSelectedPermission(val)}
        type={type}
        required
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
          disabled={isLoading || !identifier}
        >
          {isLoading ? "Saving..." : "Save"}
        </Button>
      </div>
    </Modal>
  );
};
