import React, { useState, useEffect } from "react";
import { Button } from "../../../shared/components/button";
import { Modal } from "../../../shared/components/modal";
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

const PERMISSION_LEVELS: PermissionLevel[] = ["READ", "EDIT", "MANAGE", "NO_PERMISSIONS"];

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
  const [selectedPermission, setSelectedPermission] = useState<PermissionLevel>("READ");

  useEffect(() => {
    if (isOpen) {
      setSelectedUsername("");
      setSelectedPermission("READ");
    }
  }, [isOpen]);

  const handleSave = async () => {
    if (!selectedUsername) return;
    await onSave(selectedUsername, selectedPermission);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <div>
        <label
          htmlFor="username-select"
          className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
        >
          {label}*
        </label>
        <select
          id="username-select"
          value={selectedUsername}
          onChange={(e) => setSelectedUsername(e.target.value)}
          required
          className="w-full px-3 py-2 border rounded-md focus:outline-none 
                                   text-ui-text dark:text-ui-text-dark
                                   bg-ui-bg dark:bg-ui-secondary-bg-dark
                                   border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                                   focus:border-btn-primary dark:focus:border-btn-primary-dark
                                   transition duration-150 ease-in-out cursor-pointer"
        >
          <option value="" disabled>Select {label.toLowerCase()}...</option>
          {options.map((option) => {
            const optLabel = typeof option === "string" ? option : option.label;
            const optValue = typeof option === "string" ? option : option.value;
            return (
              <option key={optValue} value={optValue}>
                {optLabel}
              </option>
            );
          })}
        </select>
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
          value={selectedPermission}
          onChange={(e) => setSelectedPermission(e.target.value as PermissionLevel)}
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
        <Button onClick={() => { void handleSave(); }} variant="primary" disabled={isLoading || !selectedUsername}>
          {isLoading ? "Saving..." : "Save"}
        </Button>
      </div>
    </Modal>
  );
};
