import React, { useState, useEffect } from "react";
import { Button } from "../../../shared/components/button";
import { faXmark } from "@fortawesome/free-solid-svg-icons";
import type {
  PermissionLevel,
  PermissionType,
  PermissionItem,
} from "../../../shared/types/entity";

interface EditPermissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (newPermission: PermissionLevel) => Promise<void>;
  item: PermissionItem | null;
  username: string;
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
  type,
  isLoading = false,
}) => {
  const [selectedPermission, setSelectedPermission] = useState<PermissionLevel>(
    item?.permission || "READ"
  );

  useEffect(() => {
    if (isOpen && item) {
      setSelectedPermission(item.permission);
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
    await onSave(selectedPermission);
  };
  
  const formattedType = type.charAt(0).toUpperCase() + type.slice(1, -1);

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
            Edit {formattedType} {item.name} permissions for {username}
          </h4>
        </div>

        <div className="space-y-6">
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
