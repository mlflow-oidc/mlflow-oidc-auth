import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import type { Webhook } from "../../../shared/types/entity";

interface DeleteWebhookModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  webhook: Webhook | null;
  isProcessing: boolean;
}

export const DeleteWebhookModal = ({
  isOpen,
  onClose,
  onConfirm,
  webhook,
  isProcessing,
}: DeleteWebhookModalProps) => {
  if (!webhook) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Delete Webhook">
      <div className="text-ui-text dark:text-ui-text-dark">
        <p className="mb-4">
          The following webhook will be permanently deleted: <span className="font-bold">{webhook.name}</span>.
        </p>
        <div className="p-3 mb-6 space-y-2 text-sm">
           <div className="flex">
             <span className="w-16 font-semibold opacity-70">ID:</span>
             <span className="font-mono">{webhook.webhook_id}</span>
           </div>
           <div className="flex">
             <span className="w-16 font-semibold opacity-70">URL:</span>
             <span className="truncate">{webhook.url}</span>
           </div>
        </div>
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
