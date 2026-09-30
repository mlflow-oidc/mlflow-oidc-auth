import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import type { WorkspaceRule } from "../../../shared/types/entity";

interface DeleteWorkspaceRuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  rule: WorkspaceRule | null;
  isProcessing: boolean;
}

export const DeleteWorkspaceRuleModal = ({
  isOpen,
  onClose,
  onConfirm,
  rule,
  isProcessing,
}: DeleteWorkspaceRuleModalProps) => {
  if (!rule) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Delete Workspace Rule">
      <div className="text-ui-text dark:text-ui-text-dark">
        <p className="mb-4">
          The following rule will be permanently deleted:{" "}
          <span className="font-bold">{rule.name}</span>.
        </p>
        <div className="p-3 mb-4 space-y-2 text-sm">
          <div className="flex">
            <span className="w-24 font-semibold opacity-70">Pattern:</span>
            <span className="font-mono break-all">{rule.pattern}</span>
          </div>
          <div className="flex">
            <span className="w-24 font-semibold opacity-70">Permission:</span>
            <span>{rule.permission}</span>
          </div>
        </div>
        <p className="mb-6 text-sm">
          Every workspace permission this rule granted is removed. Grants made
          by hand stay.
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
