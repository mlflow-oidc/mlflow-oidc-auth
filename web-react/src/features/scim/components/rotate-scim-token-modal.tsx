import React from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import type { ScimToken } from "../../../shared/types/scim";

interface RotateScimTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  token: ScimToken | null;
  isProcessing: boolean;
}

export const RotateScimTokenModal: React.FC<RotateScimTokenModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  token,
  isProcessing,
}) => {
  if (!token) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Rotate SCIM token">
      <div className="text-ui-text dark:text-ui-text-dark">
        <p className="mb-2">
          A new token will be issued to replace{" "}
          <span className="font-bold">{token.name}</span>.
        </p>
        <p className="mb-4 text-sm opacity-80">
          The current token keeps working for a short overlap window after
          rotation, so you can update your identity provider before it stops
          being accepted. The new token&apos;s plaintext is shown once, right
          after rotation.
        </p>
        <div className="flex justify-end space-x-3">
          <Button variant="ghost" onClick={onClose} disabled={isProcessing}>
            Cancel
          </Button>
          <Button variant="primary" onClick={onConfirm} disabled={isProcessing}>
            {isProcessing ? "Rotating..." : "Rotate token"}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
