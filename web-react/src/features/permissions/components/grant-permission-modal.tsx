import React, { useState, useEffect } from "react";
import { Button } from "../../../shared/components/button";
import { faXmark } from "@fortawesome/free-solid-svg-icons";
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
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
    }

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSave = async () => {
    if (!selectedUsername) return;
    await onSave(selectedUsername, selectedPermission);
  };

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto bg-ui-bg-dark/50 dark:bg-ui-bg-dark/70 transition-opacity flex justify-center items-start pt-16 sm:pt-24 md:items-center md:pt-0"
      onClick={onClose}
    >
      <div
        className="relative bg-ui-bg dark:bg-ui-bg-dark rounded-lg shadow-xl w-full max-w-xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute top-0.5 right-1">
          <Button
            onClick={onClose}
            aria-label="Close modal"
            variant="ghost"
            icon={faXmark}
          />
        </div>

        <div className="mb-4">
          <h4 className="text-lg text-ui-text dark:text-ui-text-dark font-semibold">
            {title}
          </h4>
        </div>

        <div className="space-y-6">
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
        </div>
      </div>
    </div>
  );
};
