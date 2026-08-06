import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";

interface DeleteWorkspaceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  workspace: { name: string; description: string } | null;
  isProcessing: boolean;
}

export const DeleteWorkspaceModal = ({
  isOpen,
  onClose,
  onConfirm,
  workspace,
  isProcessing,
}: DeleteWorkspaceModalProps) => {
  if (!workspace) return null;

  const isDefault = workspace.name === "default";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Delete Workspace">
      <div className="text-ui-text dark:text-ui-text-dark">
        {isDefault ? (
          <p className="mb-6 text-red-500 font-semibold">
            The default workspace cannot be deleted.
          </p>
        ) : (
          <>
            <p className="mb-4">
              The following workspace will be permanently deleted:{" "}
              <span className="font-bold">{workspace.name}</span>.
            </p>
            <p className="mb-6 text-sm text-red-500">
              All associated permissions will be removed. This action cannot be
              undone.
            </p>
          </>
        )}
        <div className="flex justify-end space-x-3">
          <Button variant="ghost" onClick={onClose} disabled={isProcessing}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={onConfirm}
            disabled={isProcessing || isDefault}
          >
            {isProcessing ? "Deleting..." : "Delete Permanently"}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
