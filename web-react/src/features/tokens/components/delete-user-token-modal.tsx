import React from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import type { UserToken } from "../../../shared/types/user";

interface DeleteUserTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  token: UserToken | null;
  isProcessing: boolean;
}

/** Confirmation before deleting one API token. */
export const DeleteUserTokenModal: React.FC<DeleteUserTokenModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  token,
  isProcessing,
}) => {
  if (!token) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Delete token">
      <div className="text-ui-text dark:text-ui-text-dark">
        <p className="mb-4">
          The token <span className="font-bold">{token.name}</span> will be
          deleted and stop working immediately. Anything still using it will
          fail to authenticate.
        </p>
        <div className="flex justify-end space-x-3">
          <Button variant="ghost" onClick={onClose} disabled={isProcessing}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={isProcessing}>
            {isProcessing ? "Deleting..." : "Delete token"}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
