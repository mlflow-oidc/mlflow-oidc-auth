import { Modal } from "../../shared/components/modal";
import { Button } from "../../shared/components/button";

interface TrashItem {
  id: string;
  name: string;
  [key: string]: unknown;
}

interface RemoveFromTrashModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  items: TrashItem[];
  itemType: "experiments" | "runs";
  isProcessing: boolean;
}

export const RemoveFromTrashModal = ({
  isOpen,
  onClose,
  onConfirm,
  items,
  itemType,
  isProcessing,
}: RemoveFromTrashModalProps) => {
  return (
    <Modal
        isOpen={isOpen}
        onClose={onClose}
        title="Remove from trash"
    >
        <div className="text-ui-text dark:text-ui-text-dark">
            <p className="mb-4">
                The following {itemType === "experiments" ? "experiment(s)" : "run(s)"} will be permanently deleted:
            </p>
            <ul className="list-disc pl-5 max-h-60 overflow-y-auto mb-6 space-y-1">
                {items.map((item) => (
                    <li key={item.id} className="text-sm">
                        <span className="font-medium">{item.name}</span> <span className="text-ui-text-secondary dark:text-ui-text-secondary-dark">(ID: {item.id})</span>
                    </li>
                ))}
            </ul>
            <div className="flex justify-end space-x-3">
                <Button variant="secondary" onClick={onClose}>
                    Cancel
                </Button>
                <Button variant="danger-outline" onClick={onConfirm} disabled={isProcessing}>
                    Delete Permanently
                </Button>
            </div>
        </div>
    </Modal>
  );
};
