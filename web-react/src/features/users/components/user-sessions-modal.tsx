import { useCallback, useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { useToast } from "../../../shared/components/toast/use-toast";
import { extractErrorMessage } from "../../../core/services/http";
import { formatDateTime } from "../../../shared/utils/format-date-time";
import { useUserSessions } from "../hooks/use-user-sessions";
import {
  revokeAllUserSessions,
  revokeUserSession,
} from "../services/user-session-service";
import type { UserSession } from "../../../shared/types/user";

interface UserSessionsModalProps {
  /** The user whose sessions to show; null closes the modal. */
  username: string | null;
  onClose: () => void;
}

type PendingRevoke = { kind: "one"; session: UserSession } | { kind: "all" };

const cellClass = "py-2 px-3 align-top";
const headClass = "py-2 px-3 font-medium";

/**
 * A user's live sessions with per-session and revoke-all actions (issue #325). Every revoke
 * asks for confirmation first; the list is re-read from the server after each one.
 */
export function UserSessionsModal({ username, onClose }: UserSessionsModalProps) {
  const { sessions, isLoading, error, refresh } = useUserSessions(username);
  const { showToast } = useToast();
  const [pending, setPending] = useState<PendingRevoke | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleClose = useCallback(() => {
    setPending(null);
    onClose();
  }, [onClose]);

  const handleConfirm = useCallback(async () => {
    if (!username || !pending) return;
    setIsProcessing(true);
    try {
      if (pending.kind === "one") {
        await revokeUserSession(username, pending.session.pk);
        showToast(`Session ${pending.session.session_id_prefix}… revoked`, "success");
      } else {
        const { revoked } = await revokeAllUserSessions(username);
        showToast(
          `${revoked} session${revoked === 1 ? "" : "s"} of ${username} revoked`,
          "success",
        );
      }
    } catch (err) {
      showToast(extractErrorMessage(err, "Failed to revoke session"), "error");
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
      title={`Sessions of ${username}`}
      width="max-w-3xl"
    >
      <div className="text-ui-text dark:text-ui-text-dark">
        <p className="mb-3 text-sm opacity-80">
          Live sign-in sessions. Revoking one signs that browser out on its next
          request; the account, its permissions and its access token are not
          affected.
        </p>

        {isLoading && <p className="text-sm opacity-70">Loading sessions...</p>}
        {!isLoading && error && (
          <p className="text-sm text-status-danger dark:text-status-danger-dark">
            {extractErrorMessage(error, "Failed to load sessions")}
          </p>
        )}
        {!isLoading && !error && sessions.length === 0 && (
          <p className="text-sm opacity-70">No live sessions.</p>
        )}

        {!isLoading && !error && sessions.length > 0 && (
          <div className="overflow-x-auto mb-4">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-ui-border dark:border-ui-border-dark">
                  <th className={headClass}>Session</th>
                  <th className={headClass}>Provider</th>
                  <th className={headClass}>Signed in</th>
                  <th className={headClass}>Last seen</th>
                  <th className={headClass}>Expires</th>
                  <th className={headClass}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr
                    key={session.pk}
                    data-testid={`session-${session.pk}`}
                    className="border-b border-ui-border dark:border-ui-border-dark"
                  >
                    <td className={`${cellClass} font-mono`}>{session.session_id_prefix}…</td>
                    <td className={cellClass}>{session.provider_id ?? "-"}</td>
                    <td className={cellClass}>{formatDateTime(session.created_at)}</td>
                    <td className={cellClass}>{formatDateTime(session.last_seen_at)}</td>
                    <td className={cellClass}>{formatDateTime(session.expires_at)}</td>
                    <td className={cellClass}>
                      <Button
                        variant="danger"
                        onClick={() => setPending({ kind: "one", session })}
                        disabled={isProcessing}
                        aria-label={`Revoke session ${session.session_id_prefix}`}
                      >
                        Revoke
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
            aria-label="Confirm revocation"
            className="mb-4 p-3 rounded border border-red-300 bg-red-50 text-red-800 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300 text-sm"
          >
            <p className="mb-3">
              {pending.kind === "one"
                ? `Revoke session ${pending.session.session_id_prefix}… of ${username}?`
                : `Revoke all ${sessions.length} sessions of ${username}? They will be signed out everywhere.`}
            </p>
            <div className="flex justify-end space-x-3">
              <Button variant="ghost" onClick={() => setPending(null)} disabled={isProcessing}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  void handleConfirm();
                }}
                disabled={isProcessing}
              >
                {isProcessing ? "Revoking..." : "Confirm revoke"}
              </Button>
            </div>
          </div>
        )}

        <div className="flex justify-end space-x-3">
          <Button variant="ghost" onClick={handleClose} disabled={isProcessing}>
            Close
          </Button>
          <Button
            variant="danger"
            onClick={() => setPending({ kind: "all" })}
            disabled={isProcessing || isLoading || sessions.length === 0}
          >
            Revoke all
          </Button>
        </div>
      </div>
    </Modal>
  );
}
