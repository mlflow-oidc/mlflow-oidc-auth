import React from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";

interface RevokeAllUserTokensModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  username: string;
  tokenCount: number;
  isProcessing: boolean;
}

/** Confirmation before an admin revokes every API token of an account. */
export const RevokeAllUserTokensModal: React.FC<
  RevokeAllUserTokensModalProps
> = ({ isOpen, onClose, onConfirm, username, tokenCount, isProcessing }) => (
  <Modal isOpen={isOpen} onClose={onClose} title="Revoke all tokens">
    <div className="text-ui-text dark:text-ui-text-dark">
      <p className="mb-4">
        All {tokenCount} token{tokenCount === 1 ? "" : "s"} of{" "}
        <span className="font-bold">{username}</span> will be revoked and stop
        working immediately. Sign-in sessions are not affected.
      </p>
      <div className="flex justify-end space-x-3">
        <Button variant="ghost" onClick={onClose} disabled={isProcessing}>
          Cancel
        </Button>
        <Button variant="danger" onClick={onConfirm} disabled={isProcessing}>
          {isProcessing ? "Revoking..." : "Revoke all tokens"}
        </Button>
      </div>
    </div>
  </Modal>
);
