import { useCallback, useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { useToast } from "../../../shared/components/toast/use-toast";
import { extractErrorMessage } from "../../../core/services/http";
import { useUserIdentities } from "../hooks/use-user-identities";
import {
  unbindUserIdentity,
  type UserIdentity,
} from "../services/user-identity-service";

interface UserIdentitiesModalProps {
  /** The user whose identities to show; null closes the modal. */
  username: string | null;
  onClose: () => void;
}

const cellClass = "py-2 px-3 align-top";
const headClass = "py-2 px-3 font-medium";

/**
 * The `(provider, subject)` identities bound to a user, each with an unbind action behind a
 * confirmation. Unbinding lets a changed subject — a re-created client, a CI workflow issuing a
 * new `sub` — bind again on the next login, or on first bearer use for a provider that adopts
 * unbound accounts.
 */
export function UserIdentitiesModal({
  username,
  onClose,
}: UserIdentitiesModalProps) {
  const { identities, isLoading, error, refresh } = useUserIdentities(username);
  const { showToast } = useToast();
  const [pending, setPending] = useState<UserIdentity | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleClose = useCallback(() => {
    setPending(null);
    onClose();
  }, [onClose]);

  const handleConfirm = useCallback(async () => {
    if (!username || !pending) return;
    setIsProcessing(true);
    try {
      await unbindUserIdentity(username, pending);
      showToast(
        `Identity ${pending.provider_id} / ${pending.subject} unbound from ${username}`,
        "success",
      );
    } catch (err) {
      showToast(extractErrorMessage(err, "Failed to unbind identity"), "error");
    } finally {
      setIsProcessing(false);
      setPending(null);
      refresh();
    }
  }, [username, pending, showToast, refresh]);

  if (!username) return null;

  return (
    <Modal
      isOpen={!!username}
      onClose={handleClose}
      title={`Identities of ${username}`}
      width="max-w-3xl"
    >
      <div className="text-ui-text dark:text-ui-text-dark">
        <p className="mb-3 text-sm opacity-80">
          The provider identities that sign in as this account. Unbind one when
          its subject has changed, so the new one can be bound on the next
          sign-in; the account and its permissions are kept.
        </p>

        {isLoading && (
          <p className="text-sm opacity-70">Loading identities...</p>
        )}
        {!isLoading && error && (
          <p className="text-sm text-status-danger dark:text-status-danger-dark">
            {extractErrorMessage(error, "Failed to load identities")}
          </p>
        )}
        {!isLoading && !error && identities.length === 0 && (
          <p className="text-sm opacity-70">No identities bound.</p>
        )}

        {!isLoading && !error && identities.length > 0 && (
          <div className="overflow-x-auto mb-4">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-ui-border dark:border-ui-border-dark">
                  <th className={headClass}>Provider</th>
                  <th className={headClass}>Subject</th>
                  <th className={headClass}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {identities.map((identity) => (
                  <tr
                    key={`${identity.provider_id}\u001f${identity.subject}`}
                    className="border-b border-ui-border dark:border-ui-border-dark"
                  >
                    <td className={cellClass}>{identity.provider_id}</td>
                    <td className={`${cellClass} font-mono break-all`}>
                      {identity.subject}
                    </td>
                    <td className={cellClass}>
                      <Button
                        variant="danger"
                        onClick={() => setPending(identity)}
                        disabled={isProcessing}
                        aria-label={`Unbind ${identity.provider_id} identity ${identity.subject}`}
                      >
                        Unbind
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {pending && (
          <div
            role="alertdialog"
            aria-label="Confirm unbinding"
            className="mb-4 p-3 rounded border border-red-300 bg-red-50 text-red-800 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300 text-sm"
          >
            <p className="mb-3">
              {`Unbind ${pending.provider_id} identity ${pending.subject} from ${username}? It will no longer sign in as this account until it is bound again.`}
            </p>
            <div className="flex justify-end space-x-3">
              <Button
                variant="ghost"
                onClick={() => setPending(null)}
                disabled={isProcessing}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  void handleConfirm();
                }}
                disabled={isProcessing}
              >
                {isProcessing ? "Unbinding..." : "Confirm unbind"}
              </Button>
            </div>
          </div>
        )}

        <div className="flex justify-end">
          <Button variant="ghost" onClick={handleClose} disabled={isProcessing}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
}
