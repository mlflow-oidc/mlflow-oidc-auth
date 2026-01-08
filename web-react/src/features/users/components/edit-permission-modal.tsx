import React, { useState, useEffect } from "react";
import { Button } from "../../../shared/components/button";
import { faXmark } from "@fortawesome/free-solid-svg-icons";
import type {
  PermissionLevel,
  PermissionType,
  AnyPermissionItem,
} from "../../../shared/types/entity";

interface EditPermissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (newPermission: PermissionLevel, regex?: string, priority?: number) => Promise<void>;
  item: AnyPermissionItem | null;
  username: string;
  resourceId?: string;
  type: PermissionType;
  isLoading?: boolean;
}

const PERMISSION_LEVELS: PermissionLevel[] = ["READ", "EDIT", "MANAGE", "NO_PERMISSIONS"];

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
    item?.permission || "READ"
  );
  const [regex, setRegex] = useState<string>(
    item && "regex" in item ? item.regex : ""
  );
  const [priority, setPriority] = useState<number>(
    item && "priority" in item ? item.priority : 0
  );

  useEffect(() => {
    if (isOpen && item) {
      setSelectedPermission(item.permission);
      if ("regex" in item) {
        setRegex(item.regex);
        setPriority(item.priority);
      }
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen, item]);

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
          {isRegexRule && (
            <>
              <div>
                <label
                  htmlFor="regex-pattern"
                  className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
                >
                  Regex Pattern
                </label>
                <input
                  type="text"
                  id="regex-pattern"
                  value={regex}
                  onChange={(e) => setRegex(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md focus:outline-none 
                                           text-ui-text dark:text-ui-text-dark
                                           bg-ui-bg dark:bg-ui-secondary-bg-dark
                                           border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                                           focus:border-btn-primary dark:focus:border-btn-primary-dark
                                           transition duration-150 ease-in-out
                                           opacity-70 cursor-not-allowed"
                  required
                  readOnly
                />
              </div>
              <div>
                <label
                  htmlFor="priority"
                  className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
                >
                  Priority
                </label>
                <input
                  type="number"
                  id="priority"
                  value={priority}
                  onChange={(e) => setPriority(parseInt(e.target.value, 10))}
                  className="w-full px-3 py-2 border rounded-md focus:outline-none 
                                           text-ui-text dark:text-ui-text-dark
                                           bg-ui-bg dark:bg-ui-secondary-bg-dark
                                           border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                                           focus:border-btn-primary dark:focus:border-btn-primary-dark
                                           transition duration-150 ease-in-out"
                  required
                />
              </div>
            </>
          )}

          <div>
            <label
              htmlFor="permission-level"
              className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
            >
              Permission Level
            </label>
            <select
              id="permission-level"
              value={selectedPermission}
              onChange={(e) => setSelectedPermission(e.target.value as PermissionLevel)}
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
            <Button onClick={() => { void handleSave(); }} variant="primary" disabled={isLoading}>
              {isLoading ? "Saving..." : "Ok"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
