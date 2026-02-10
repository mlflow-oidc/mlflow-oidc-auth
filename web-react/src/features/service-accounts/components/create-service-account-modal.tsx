import React, { useState, useEffect, useRef } from "react";
import { Button } from "../../../shared/components/button";
import { Modal } from "../../../shared/components/modal";
import { Input } from "../../../shared/components/input";

interface CreateServiceAccountModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: {
    name: string;
    display_name: string;
    is_admin: boolean;
  }) => void | Promise<void>;
}

export const CreateServiceAccountModal: React.FC<
  CreateServiceAccountModalProps
> = ({ isOpen, onClose, onSave }) => {
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [isDisplayNameManual, setIsDisplayNameManual] = useState(false);

  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      // Set focus when modal opens
      const timer = setTimeout(() => nameInputRef.current?.focus(), 0);
      return () => clearTimeout(timer);
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
      <div className="space-y-4">
        <Input
          ref={nameInputRef}
          id="service-account-name"
          label="Service Account Name*"
          type="text"
          value={name}
          onChange={handleNameChange}
          placeholder="my-service-account"
          required
        />
        <Input
          id="display-name"
          label="Display Name*"
          type="text"
          value={displayName}
          onChange={handleDisplayNameChange}
          placeholder="My Service Account"
          required
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
