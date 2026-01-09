import React, { useState, useEffect } from "react";
import { Button } from "../../../shared/components/button";
import { Modal } from "../../../shared/components/modal";
import type { PermissionLevel } from "../../../shared/types/entity";

interface AddRegexRuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (regex: string, permission: PermissionLevel, priority: number) => Promise<void>;
  isLoading?: boolean;
}

const PERMISSION_LEVELS: PermissionLevel[] = ["READ", "EDIT", "MANAGE", "NO_PERMISSIONS"];

export const AddRegexRuleModal: React.FC<AddRegexRuleModalProps> = ({
  isOpen,
  onClose,
  onSave,
  isLoading = false,
}) => {
  const [regex, setRegex] = useState("");
  const [priority, setPriority] = useState<number>(100);
  const [permission, setPermission] = useState<PermissionLevel>("READ");
  const [errors, setErrors] = useState<{ regex?: string; priority?: string }>({});

  useEffect(() => {
    if (isOpen) {
      setRegex("");
      setPriority(100);
      setPermission("READ");
      setErrors({});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async () => {
    const newErrors: { regex?: string; priority?: string } = {};
    let hasError = false;

    try {
      new RegExp(regex);
    } catch {
      newErrors.regex = "Invalid regular expression. Please enter a valid Python regex.";
      hasError = true;
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
      <div>
        <label
          htmlFor="regex-input"
          className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
        >
          Regex*
        </label>
        <input
          id="regex-input"
          type="text"
          value={regex}
          onChange={(e) => {
            setRegex(e.target.value);
            if (errors.regex) setErrors({ ...errors, regex: undefined });
          }}
          required
          placeholder="Enter Python Regex e.g. (^test_.*)"
          className={`w-full px-3 py-2 border rounded-md focus:outline-none 
                                   text-ui-text dark:text-ui-text-dark
                                   bg-ui-bg dark:bg-ui-secondary-bg-dark
                                   ${
                                     errors.regex
                                       ? "border-status-danger focus:border-status-danger"
                                       : "border-ui-secondary-bg dark:border-ui-secondary-bg-dark focus:border-btn-primary dark:focus:border-btn-primary-dark"
                                   }
                                   transition duration-150 ease-in-out`}
        />
        <p className={`mt-1 text-sm text-status-danger dark:text-status-danger-dark ${errors.regex ? "" : "invisible"}`}>
          {errors.regex || "\u00A0"}
        </p>
      </div>

      <div>
        <label
          htmlFor="priority-input"
          className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
        >
          Priority*
        </label>
        <input
          id="priority-input"
          type="number"
          value={isNaN(priority) ? "" : priority}
          onChange={(e) => {
            setPriority(parseInt(e.target.value, 10));
            if (errors.priority)
              setErrors({ ...errors, priority: undefined });
          }}
          required
          step="1"
          min="0"
          className={`w-full px-3 py-2 border rounded-md focus:outline-none 
                                   text-ui-text dark:text-ui-text-dark
                                   bg-ui-bg dark:bg-ui-secondary-bg-dark
                                   ${
                                     errors.priority
                                       ? "border-status-danger focus:border-status-danger"
                                       : "border-ui-secondary-bg dark:border-ui-secondary-bg-dark focus:border-btn-primary dark:focus:border-btn-primary-dark"
                                   }
                                   transition duration-150 ease-in-out`}
        />
        <p className={`mt-1 text-sm text-status-danger dark:text-status-danger-dark ${errors.priority ? "" : "invisible"}`}>
          {errors.priority || "\u00A0"}
        </p>
      </div>

      <div>
        <label
          htmlFor="permission-level"
          className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
        >
          Permissions*
        </label>
        <select
          id="permission-level"
          value={permission}
          onChange={(e) => setPermission(e.target.value as PermissionLevel)}
          required
          className="w-full px-3 py-2 border rounded-md focus:outline-none 
                                   text-ui-text dark:text-ui-text-dark
                                   bg-ui-bg dark:bg-ui-secondary-bg-dark
                                   border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                                   focus:border-btn-primary dark:focus:border-btn-primary-dark
                                   transition duration-150 ease-in-out cursor-pointer"
        >
          {PERMISSION_LEVELS.map((level) => (
            <option key={level} value={level}>
              {level}
            </option>
          ))}
        </select>
      </div>

      <div className="flex justify-end space-x-3">
        <Button onClick={onClose} variant="ghost" disabled={isLoading}>
          Cancel
        </Button>
        <Button 
            onClick={() => { void handleSave(); }} 
            variant="primary" 
            disabled={isLoading}
        >
          {isLoading ? "Saving..." : "Save"}
        </Button>
      </div>
    </Modal>
  );
};
