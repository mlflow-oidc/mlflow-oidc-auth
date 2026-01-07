import React, { useState, useEffect } from "react";
import { Button } from "../../../shared/components/button";
import { faXmark } from "@fortawesome/free-solid-svg-icons";
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

  useEffect(() => {
    if (isOpen) {
      setRegex("");
      setPriority(100);
      setPermission("READ");
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
    if (!regex || priority === undefined) return;
    await onSave(regex, permission, priority);
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
            Add New Regex Rule
          </h4>
        </div>

        <div className="space-y-6">
          <div>
            <label
              htmlFor="regex-input"
              className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
            >
              Regex (Enter Python Regex)*
            </label>
            <input
              id="regex-input"
              type="text"
              value={regex}
              onChange={(e) => setRegex(e.target.value)}
              required
              placeholder="e.g. ^test_.*"
              className="w-full px-3 py-2 border rounded-md focus:outline-none 
                                       text-ui-text dark:text-ui-text-dark
                                       bg-ui-bg dark:bg-ui-secondary-bg-dark
                                       border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                                       focus:border-btn-primary dark:focus:border-btn-primary-dark
                                       transition duration-150 ease-in-out"
            />
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
              value={priority}
              onChange={(e) => setPriority(parseInt(e.target.value, 10))}
              required
              step="1"
              className="w-full px-3 py-2 border rounded-md focus:outline-none 
                                       text-ui-text dark:text-ui-text-dark
                                       bg-ui-bg dark:bg-ui-secondary-bg-dark
                                       border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                                       focus:border-btn-primary dark:focus:border-btn-primary-dark
                                       transition duration-150 ease-in-out"
            />
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
                disabled={isLoading || !regex || priority === undefined}
            >
              {isLoading ? "Saving..." : "Save"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
