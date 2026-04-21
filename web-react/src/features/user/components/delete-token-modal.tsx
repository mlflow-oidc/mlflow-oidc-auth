import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import type { UserToken } from "../../../core/services/token-service";

interface DeleteTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  token: UserToken | null;
  isProcessing: boolean;
}

export const DeleteTokenModal = ({
  isOpen,
  onClose,
  onConfirm,
  token,
  isProcessing,
}: DeleteTokenModalProps) => {
  if (!token) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Delete Token">
      <div className="text-ui-text dark:text-ui-text-dark">
        <p className="mb-4">
          The following token will be permanently deleted:{" "}
          <span className="font-bold">{token.name}</span>.
        </p>
        <p className="mb-6 text-sm text-text-secondary dark:text-text-secondary-dark">
          This action cannot be undone. Any applications using this token will
          lose access.
        </p>
        <div className="flex justify-end space-x-3">
          <Button variant="ghost" onClick={onClose} disabled={isProcessing}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={isProcessing}>
            {isProcessing ? "Deleting..." : "Delete Permanently"}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
