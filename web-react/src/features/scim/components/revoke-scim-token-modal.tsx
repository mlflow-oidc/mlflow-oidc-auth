import React from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import type { ScimToken } from "../../../shared/types/scim";

interface RevokeScimTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  token: ScimToken | null;
  isProcessing: boolean;
}

export const RevokeScimTokenModal: React.FC<RevokeScimTokenModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  token,
  isProcessing,
}) => {
  if (!token) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Revoke SCIM token">
      <div className="text-ui-text dark:text-ui-text-dark">
        <p className="mb-4">
          <span className="font-bold">{token.name}</span> will stop working
          immediately. Any identity provider using it will be unable to
          synchronize users until a new token is issued.
        </p>
        <div className="flex justify-end space-x-3">
          <Button variant="ghost" onClick={onClose} disabled={isProcessing}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={isProcessing}>
            {isProcessing ? "Revoking..." : "Revoke token"}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
