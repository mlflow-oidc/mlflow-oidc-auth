import { useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { Switch } from "../../../shared/components/switch";
import { describeManagedBy } from "../../../shared/utils/managed-by";
import type { UserDetails } from "../../../shared/types/user";

interface DeactivateUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (adminOverride: boolean) => void;
  user: UserDetails | null;
  isProcessing: boolean;
}

export const DeactivateUserModal = ({
  isOpen,
  onClose,
  onConfirm,
  user,
  isProcessing,
}: DeactivateUserModalProps) => {
  const [adminOverride, setAdminOverride] = useState(false);
  const [lastUsername, setLastUsername] = useState<string | null>(
    user?.username ?? null,
  );

  // Reset the override switch whenever a new user is targeted, derived
  // during render rather than in an effect (see webhook-status-switch.tsx
  // for the same pattern).
  if ((user?.username ?? null) !== lastUsername) {
    setLastUsername(user?.username ?? null);
    setAdminOverride(false);
  }

  if (!user) return null;

  const { bucket, label } = describeManagedBy(user.managed_by);
  const isDirectoryManaged = bucket === "scim" || bucket === "oidc";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Deactivate User">
      <div className="text-ui-text dark:text-ui-text-dark">
        <p className="mb-4">
          <span className="font-bold">{user.username}</span> will be
          deactivated. Their sessions and access tokens are revoked
          immediately; existing permission grants are kept, so reactivating
          restores access.
        </p>

        {isDirectoryManaged && (
          <div className="mb-4 p-3 rounded border border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-300 text-sm space-y-3">
            <p>
              This account is managed by <span className="font-semibold">{label}</span>
              . The directory owns this account, and a future sync may
              overwrite this change unless you override the ownership guard.
            </p>
            <Switch
              checked={adminOverride}
              onChange={setAdminOverride}
              label="Override ownership guard"
              disabled={isProcessing}
            />
          </div>
        )}

        <div className="flex justify-end space-x-3">
          <Button variant="ghost" onClick={onClose} disabled={isProcessing}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => onConfirm(adminOverride)}
            disabled={isProcessing}
          >
            {isProcessing ? "Deactivating..." : "Deactivate"}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
