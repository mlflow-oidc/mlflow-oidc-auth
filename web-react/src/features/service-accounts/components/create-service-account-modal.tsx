import React, { useState, useEffect, useRef } from "react";
import { Button } from "../../../shared/components/button";
import { Modal } from "../../../shared/components/modal";

interface CreateServiceAccountModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: {
    name: string;
    display_name: string;
    is_admin: boolean;
  }) => void | Promise<void>;
}

export const CreateServiceAccountModal: React.FC<CreateServiceAccountModalProps> = ({
  isOpen,
  onClose,
  onSave,
}) => {
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [isDisplayNameManual, setIsDisplayNameManual] = useState(false);

  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setName("");
      setDisplayName("");
      setIsAdmin(false);
      setIsDisplayNameManual(false);
      // Focus the first input when modal opens
      setTimeout(() => nameInputRef.current?.focus(), 0);
    }
  }, [isOpen]);

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setName(value);
    if (!isDisplayNameManual) {
      setDisplayName(value);
    }
  };

  const handleDisplayNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setDisplayName(e.target.value);
    setIsDisplayNameManual(true);
  };

  const handleSave = async () => {
    if (!name || !displayName) return;
    await onSave({
      name,
      display_name: displayName,
      is_admin: isAdmin,
    });
    onClose();
  };

  const isFormValid = name.trim() !== "" && displayName.trim() !== "";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Service Account">
      <div>
        <label
          htmlFor="sa-name"
          className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1.5"
        >
          Service Account Name*
        </label>
        <input
          ref={nameInputRef}
          id="sa-name"
          type="text"
          value={name}
          onChange={handleNameChange}
          required
          className="w-full px-3 py-2 border rounded-md focus:outline-none 
                                   text-ui-text dark:text-ui-text-dark
                                   bg-ui-bg dark:bg-ui-secondary-bg-dark
                                   border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                                   focus:border-btn-primary dark:focus:border-btn-primary-dark
                                   transition duration-150 ease-in-out"
          placeholder="Enter service account name"
        />
      </div>

      <div>
        <label
          htmlFor="display-name"
          className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1.5"
        >
          Display Name*
        </label>
        <input
          id="display-name"
          type="text"
          value={displayName}
          onChange={handleDisplayNameChange}
          required
          className="w-full px-3 py-2 border rounded-md focus:outline-none 
                                   text-ui-text dark:text-ui-text-dark
                                   bg-ui-bg dark:bg-ui-secondary-bg-dark
                                   border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                                   focus:border-btn-primary dark:focus:border-btn-primary-dark
                                   transition duration-150 ease-in-out"
          placeholder="Enter display name"
        />
      </div>

      <div className="flex items-center space-x-2">
        <input
          id="grant-admin"
          type="checkbox"
          checked={isAdmin}
          onChange={(e) => setIsAdmin(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300 text-btn-primary focus:ring-btn-primary"
        />
        <label
          htmlFor="grant-admin"
          className="text-sm font-medium text-text-primary dark:text-text-primary-dark cursor-pointer"
        >
          Grant Admin Privileges
        </label>
      </div>

      <div className="flex justify-end space-x-3 pt-4 border-t border-ui-secondary-bg dark:border-ui-secondary-bg-dark">
        <Button onClick={onClose} variant="ghost">
          Cancel
        </Button>
        <Button
          onClick={() => {
            void handleSave();
          }}
          variant="primary"
          disabled={!isFormValid}
        >
          Save
        </Button>
      </div>
    </Modal>
  );
};
