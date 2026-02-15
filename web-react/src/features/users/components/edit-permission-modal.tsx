import React, { useState } from "react";
import { Button } from "../../../shared/components/button";
import { Modal } from "../../../shared/components/modal";
import { Input } from "../../../shared/components/input";
import { PermissionLevelSelect } from "../../../shared/components/permission-level-select";
import type {
  PermissionLevel,
  PermissionType,
  AnyPermissionItem,
} from "../../../shared/types/entity";

interface EditPermissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (
    newPermission: PermissionLevel,
    regex?: string,
    priority?: number,
  ) => Promise<void>;
  item: AnyPermissionItem | null;
  username: string;
  resourceId?: string;
  type: PermissionType;
  isLoading?: boolean;
}

export const EditPermissionModal: React.FC<EditPermissionModalProps> = ({
  isOpen,
  onClose,
  onSave,
  item,
  username,
  resourceId,
  type,
  isLoading = false,
}) => {
  const [selectedPermission, setSelectedPermission] = useState<PermissionLevel>(
    item?.permission || "READ",
  );
  const [regex, setRegex] = useState<string>(
    item && "regex" in item ? item.regex : "",
  );
  const [priority, setPriority] = useState<number>(
    item && "priority" in item ? item.priority : 0,
  );

  if (!isOpen || !item) return null;

  const handleSave = async () => {
    if ("regex" in item) {
      await onSave(selectedPermission, regex, priority);
    } else {
      await onSave(selectedPermission);
    }
  };

  const isRegexRule = "regex" in item;
  const identifier = "name" in item ? item.name : item.regex;
  const displayResourceId = resourceId || identifier;
  const title = isRegexRule
    ? `Manage Regex Rule ${identifier}`
    : `Edit ${type.charAt(0).toUpperCase() + type.slice(1, -1)} ${displayResourceId} permissions for ${username}`;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      {isRegexRule && (
        <>
          <Input
            id="regex-pattern"
            label="Regex Pattern"
            type="text"
            value={regex}
            onChange={(e) => setRegex(e.target.value)}
            className="opacity-70 cursor-not-allowed"
            required
            readOnly
            containerClassName="mb-4"
          />
          <Input
            id="priority"
            label="Priority"
            type="number"
            value={priority}
            onChange={(e) => setPriority(parseInt(e.target.value, 10))}
            required
            containerClassName="mb-4"
          />
        </>
      )}

      <PermissionLevelSelect
        id="permission-level"
        label="Permission Level"
        value={selectedPermission}
        onChange={(val) => setSelectedPermission(val)}
        type={type}
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
          disabled={isLoading}
        >
          {isLoading ? "Saving..." : "Ok"}
        </Button>
      </div>
    </Modal>
  );
};
