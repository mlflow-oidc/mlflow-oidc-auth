import { useCallback, useState } from "react";
import { faBan, faPlus, faTrash } from "@fortawesome/free-solid-svg-icons";
import PageStatus from "../../../shared/components/page/page-status";
import { EntityListTable } from "../../../shared/components/entity-list-table";
import { SearchInput } from "../../../shared/components/search-input";
import { Button } from "../../../shared/components/button";
import { IconButton } from "../../../shared/components/icon-button";
import { useToast } from "../../../shared/components/toast/use-toast";
import { useSearch } from "../../../core/hooks/use-search";
import { extractErrorMessage } from "../../../core/services/http";
import { formatDateTime } from "../../../shared/utils/format-date-time";
import { useUserTokens } from "../hooks/use-user-tokens";
import {
  deleteUserToken,
  revokeAllUserTokens,
} from "../services/user-token-service";
import { CreateUserTokenModal } from "./create-user-token-modal";
import { DeleteUserTokenModal } from "./delete-user-token-modal";
import { RevokeAllUserTokensModal } from "./revoke-all-user-tokens-modal";
import type { ColumnConfig } from "../../../shared/types/table";
import type {
  UserToken,
  UserTokenWithSecret,
} from "../../../shared/types/user";

interface UserTokensPanelProps {
  /**
   * The account whose tokens to manage through the admin endpoints. Omit for the signed-in
   * user's own tokens. Only the admin form offers "Revoke all tokens".
   */
  username?: string;
}

/** Shown in place of a prefix for a secret carried over from the single-token scheme. */
const CARRIED_OVER_LABEL = "Carried over";
const CARRIED_OVER_TITLE =
  "Secret from before the upgrade to named tokens. Delete it if you do not use it.";

const dim = (token: UserToken) => (token.active ? "" : "opacity-50");

const columns = (
  onDelete: (token: UserToken) => void,
): ColumnConfig<UserToken>[] => [
  {
    header: "Name",
    render: (t) => (
      <span className={`truncate block ${dim(t)}`} title={t.name}>
        {t.name}
      </span>
    ),
  },
  {
    header: "Prefix",
    render: (t) =>
      t.token_prefix ? (
        <span
          className={`font-mono ${dim(t)}`}
        >{`mlf_${t.token_prefix}_…`}</span>
      ) : (
        <span
          className={`italic opacity-70 ${dim(t)}`}
          title={CARRIED_OVER_TITLE}
        >
          {CARRIED_OVER_LABEL}
        </span>
      ),
  },
  {
    header: "Created",
    render: (t) => (
      <span className={dim(t)}>{formatDateTime(t.created_at)}</span>
    ),
  },
  {
    header: "Expires",
    render: (t) => (
      <span className={dim(t)}>{formatDateTime(t.expires_at)}</span>
    ),
  },
  {
    header: "Last used",
    render: (t) => (
      <span className={dim(t)}>{formatDateTime(t.last_used_at)}</span>
    ),
  },
  {
    header: "Status",
    render: (t) =>
      t.active ? (
        <span className="font-medium text-green-600 dark:text-green-400">
          Active
        </span>
      ) : (
        <span className="font-medium text-gray-500 dark:text-gray-400">
          Expired
        </span>
      ),
  },
  {
    header: "Actions",
    render: (t) => (
      <IconButton
        icon={faTrash}
        title={`Delete token ${t.name}`}
        onClick={() => onDelete(t)}
      />
    ),
  },
];

/**
 * A table of an account's API tokens with create, delete and (admin) revoke-all actions.
 */
export function UserTokensPanel({ username }: UserTokensPanelProps) {
  const { showToast } = useToast();
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();
  const { tokens, total, pagination, isLoading, error, refresh } =
    useUserTokens(username, submittedTerm);

  // "Revoke all" acts on every token, not just those matching the search, so
  // it needs the unfiltered count: remember the last total seen without one.
  const [accountTokenCount, setAccountTokenCount] = useState(total);
  if (!submittedTerm && !isLoading && !error && total !== accountTokenCount) {
    setAccountTokenCount(total);
  }

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [deletingToken, setDeletingToken] = useState<UserToken | null>(null);
  const [isRevokeAllOpen, setIsRevokeAllOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const isAdminView = username !== undefined;

  const handleCreated = useCallback(
    (token: UserTokenWithSecret) => {
      showToast(`Token "${token.name}" created`, "success");
      refresh();
    },
    [refresh, showToast],
  );

  const handleConfirmDelete = useCallback(async () => {
    if (!deletingToken) return;
    setIsProcessing(true);
    try {
      await deleteUserToken(username, deletingToken.id);
      showToast(`Token "${deletingToken.name}" deleted`, "success");
    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          `Failed to delete token "${deletingToken.name}"`,
        ),
        "error",
      );
    } finally {
      setIsProcessing(false);
      setDeletingToken(null);
      refresh();
    }
  }, [deletingToken, username, showToast, refresh]);

  const handleConfirmRevokeAll = useCallback(async () => {
    if (username === undefined) return;
    setIsProcessing(true);
    try {
      const { revoked } = await revokeAllUserTokens(username);
      showToast(
        `${revoked} token${revoked === 1 ? "" : "s"} of ${username} revoked`,
        "success",
      );
    } catch (err) {
      showToast(extractErrorMessage(err, "Failed to revoke tokens"), "error");
    } finally {
      setIsProcessing(false);
      setIsRevokeAllOpen(false);
      refresh();
    }
  }, [username, showToast, refresh]);

  return (
    <>
      <PageStatus
        isLoading={isLoading && tokens.length === 0}
        loadingText="Loading tokens..."
        error={error}
        onRetry={refresh}
      />

      {!error && !(isLoading && tokens.length === 0) && (
        <>
          <div className="mt-2 mb-3 flex items-center gap-6">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search tokens..."
            />
            <Button
              variant="secondary"
              onClick={() => setIsCreateOpen(true)}
              icon={faPlus}
              className="whitespace-nowrap h-8 mb-1 mt-2"
            >
              Create token
            </Button>
            {isAdminView && (
              <Button
                variant="danger"
                onClick={() => setIsRevokeAllOpen(true)}
                disabled={accountTokenCount === 0}
                title={
                  accountTokenCount === 0
                    ? "This account has no tokens"
                    : undefined
                }
                icon={faBan}
                className="whitespace-nowrap h-8 mb-1 mt-2 ml-auto"
              >
                Revoke all tokens
              </Button>
            )}
          </div>

          <EntityListTable
            data={tokens}
            pagination={pagination}
            columns={columns(setDeletingToken)}
            searchTerm={submittedTerm}
          />
        </>
      )}

      {/* Outside the loading/error gate on purpose: creating a token refreshes the list, and an
          unmount mid-display would lose the plaintext token, which cannot be fetched again. */}
      <CreateUserTokenModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreated={handleCreated}
        owner={username}
      />

      <DeleteUserTokenModal
        isOpen={!!deletingToken}
        onClose={() => setDeletingToken(null)}
        onConfirm={() => {
          void handleConfirmDelete();
        }}
        token={deletingToken}
        isProcessing={isProcessing}
      />

      {isAdminView && (
        <RevokeAllUserTokensModal
          isOpen={isRevokeAllOpen}
          onClose={() => setIsRevokeAllOpen(false)}
          onConfirm={() => {
            void handleConfirmRevokeAll();
          }}
          username={username}
          tokenCount={accountTokenCount}
          isProcessing={isProcessing}
        />
      )}
    </>
  );
}
