import React, { useState } from "react";
import { Button } from "../../../shared/components/button";
import { Modal } from "../../../shared/components/modal";
import { Input } from "../../../shared/components/input";
import { Select } from "../../../shared/components/select";
import type { PermissionLevel } from "../../../shared/types/entity";

interface AddRegexRuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (
    regex: string,
    permission: PermissionLevel,
    priority: number,
  ) => Promise<void>;
  isLoading?: boolean;
}

const PERMISSION_LEVELS: PermissionLevel[] = [
  "READ",
  "EDIT",
  "MANAGE",
  "NO_PERMISSIONS",
];

export const AddRegexRuleModal: React.FC<AddRegexRuleModalProps> = ({
  isOpen,
  onClose,
  onSave,
  isLoading = false,
}) => {
  const [regex, setRegex] = useState("");
  const [priority, setPriority] = useState<number>(100);
  const [permission, setPermission] = useState<PermissionLevel>("READ");
  const [errors, setErrors] = useState<{ regex?: string; priority?: string }>(
    {},
  );

  if (!isOpen) return null;

  const handleSave = async () => {
    const newErrors: { regex?: string; priority?: string } = {};
    let hasError = false;

    if (!regex.trim()) {
      newErrors.regex = "Regex is required.";
      hasError = true;
    } else {
      try {
        new RegExp(regex);
      } catch {
        newErrors.regex =
          "Invalid regular expression. Please enter a valid Python regex.";
        hasError = true;
      }
    }

    if (priority === undefined || isNaN(priority)) {
      newErrors.priority = "Priority is required.";
      hasError = true;
    } else if (!Number.isInteger(priority) || priority < 0) {
      newErrors.priority = "Priority must be a non-negative integer.";
      hasError = true;
    }

    setErrors(newErrors);

    if (hasError) return;

    await onSave(regex, permission, priority);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add New Regex Rule">
      <Input
        id="regex-input"
        label="Regex*"
        type="text"
        value={regex}
        onChange={(e) => {
          setRegex(e.target.value);
          if (errors.regex) setErrors({ ...errors, regex: undefined });
        }}
        required
        placeholder="Enter Python Regex e.g. (^test_.*)"
        error={errors.regex}
        containerClassName="mb-4"
        reserveErrorSpace
      />

      <Input
        id="priority-input"
        label="Priority*"
        type="number"
        value={isNaN(priority) ? "" : priority}
        onChange={(e) => {
          setPriority(parseInt(e.target.value, 10));
          if (errors.priority) setErrors({ ...errors, priority: undefined });
        }}
        required
        step="1"
        min="0"
        error={errors.priority}
        containerClassName="mb-4"
        reserveErrorSpace
      />

      <Select
        id="permission-level"
        label="Permissions*"
        value={permission}
        onChange={(e) => setPermission(e.target.value as PermissionLevel)}
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
          disabled={isLoading}
        >
          {isLoading ? "Saving..." : "Save"}
        </Button>
      </div>
    </Modal>
  );
};
