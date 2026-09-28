import { useCallback, useMemo, useState } from "react";
import { faPlus, faCopy, faRotate, faBan } from "@fortawesome/free-solid-svg-icons";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { Button } from "../../shared/components/button";
import { IconButton } from "../../shared/components/icon-button";
import { useToast } from "../../shared/components/toast/use-toast";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import { useScimTokens } from "./hooks/use-scim-tokens";
import { rotateScimToken, revokeScimToken } from "./services/scim-token-service";
import { CreateScimTokenModal } from "./components/create-scim-token-modal";
import { ScimTokenSecretModal } from "./components/scim-token-secret-modal";
import { RotateScimTokenModal } from "./components/rotate-scim-token-modal";
import { RevokeScimTokenModal } from "./components/revoke-scim-token-modal";
import { ScimStatusPanel } from "./components/scim-status-panel";
import { ScimActivityTable } from "./components/scim-activity-table";
import { useScimStatus } from "./hooks/use-scim-status";
import { useScimActivity } from "./hooks/use-scim-activity";
import type { ColumnConfig } from "../../shared/types/table";
import type {
  ScimActivityOutcome,
  ScimToken,
  ScimTokenWithSecret,
} from "../../shared/types/scim";

const EXPIRING_SOON_MS = 14 * 24 * 60 * 60 * 1000;

type TokenStatus = "Active" | "Expiring" | "Expired" | "Revoked";

function getTokenStatus(token: ScimToken): TokenStatus {
  if (token.revoked_at) return "Revoked";
  if (token.expires_at) {
    const diff = new Date(token.expires_at).getTime() - Date.now();
    if (diff < 0) return "Expired";
    if (diff <= EXPIRING_SOON_MS) return "Expiring";
  }
  return "Active";
}

/** Statuses that mean a token can no longer be used to authenticate. */
function isTokenInactive(status: TokenStatus): boolean {
  return status === "Revoked" || status === "Expired";
}

const STATUS_CLASSES: Record<TokenStatus, string> = {
  Active: "text-green-600 dark:text-green-400",
  Expiring: "text-yellow-600 dark:text-yellow-400",
  Expired: "text-gray-500 dark:text-gray-400",
  Revoked: "text-status-danger dark:text-status-danger-dark",
};

function formatDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString();
}

export default function ScimPage() {
  const {
    tokens,
    isLoading,
    error,
    refresh: refreshTokens,
  } = useScimTokens();
  const {
    status,
    isLoading: isStatusLoading,
    error: statusError,
    refresh: refreshStatus,
  } = useScimStatus();
  const [outcomeFilter, setOutcomeFilter] =
    useState<ScimActivityOutcome | null>(null);
  const activity = useScimActivity(outcomeFilter);
  const refreshActivity = activity.refresh;

  // A token change shows up in the per-token status too, so both lists refresh together.
  const refresh = useCallback(() => {
    refreshTokens();
    refreshStatus();
  }, [refreshTokens, refreshStatus]);
  const { showToast } = useToast();
  const { basePath } = useRuntimeConfig();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [rotatingToken, setRotatingToken] = useState<ScimToken | null>(null);
  const [revokingToken, setRevokingToken] = useState<ScimToken | null>(null);
  const [secretToken, setSecretToken] = useState<ScimTokenWithSecret | null>(
    null,
  );
  const [isProcessing, setIsProcessing] = useState(false);

  const scimBaseUrl = `${window.location.origin}${basePath}/scim/v2`;

  const handleCopyEndpoint = useCallback(() => {
    navigator.clipboard
      .writeText(scimBaseUrl)
      .then(() => showToast("Provisioning endpoint copied", "success"))
      .catch((err) => {
        console.error("Failed to copy provisioning endpoint:", err);
        showToast("Failed to copy provisioning endpoint", "error");
      });
  }, [scimBaseUrl, showToast]);

  const handleCreated = useCallback(
    (token: ScimTokenWithSecret) => {
      setIsCreateOpen(false);
      setSecretToken(token);
      refresh();
    },
    [refresh],
  );

  const handleConfirmRotate = useCallback(async () => {
    if (!rotatingToken) return;
    setIsProcessing(true);
    try {
      const rotated = await rotateScimToken(rotatingToken.id);
      showToast(`Token "${rotatingToken.name}" rotated`, "success");
      setRotatingToken(null);
      setSecretToken(rotated);
      refresh();
    } catch (err) {
      console.error("Failed to rotate SCIM token:", err);
      showToast(`Failed to rotate token "${rotatingToken.name}"`, "error");
    } finally {
      setIsProcessing(false);
    }
  }, [rotatingToken, refresh, showToast]);

  const handleConfirmRevoke = useCallback(async () => {
    if (!revokingToken) return;
    setIsProcessing(true);
    try {
      await revokeScimToken(revokingToken.id);
      showToast(`Token "${revokingToken.name}" revoked`, "success");
      setRevokingToken(null);
      refresh();
    } catch (err) {
      console.error("Failed to revoke SCIM token:", err);
      showToast(`Failed to revoke token "${revokingToken.name}"`, "error");
    } finally {
      setIsProcessing(false);
    }
  }, [revokingToken, refresh, showToast]);

  const columns: ColumnConfig<ScimToken>[] = useMemo(
    () => [
      {
        header: "Name",
        render: (t) => (
          <span className={isTokenInactive(getTokenStatus(t)) ? "opacity-50" : ""}>
            {t.name}
          </span>
        ),
      },
      {
        header: "Prefix",
        render: (t) => (
          <span
            className={`font-mono ${isTokenInactive(getTokenStatus(t)) ? "opacity-50" : ""}`}
          >
            {t.token_prefix}
          </span>
        ),
      },
      {
        header: "Created",
        render: (t) => (
          <span className={isTokenInactive(getTokenStatus(t)) ? "opacity-50" : ""}>
            {formatDate(t.created_at)}
          </span>
        ),
      },
      {
        header: "Created by",
        render: (t) => (
          <span className={isTokenInactive(getTokenStatus(t)) ? "opacity-50" : ""}>
            {t.created_by}
          </span>
        ),
      },
      {
        header: "Last used",
        render: (t) => (
          <span className={isTokenInactive(getTokenStatus(t)) ? "opacity-50" : ""}>
            {formatDate(t.last_used_at)}
          </span>
        ),
      },
      {
        header: "Expires",
        render: (t) => (
          <span className={isTokenInactive(getTokenStatus(t)) ? "opacity-50" : ""}>
            {formatDate(t.expires_at)}
          </span>
        ),
      },
      {
        header: "Status",
        render: (t) => {
          const status = getTokenStatus(t);
          return (
            <span className={`font-medium ${STATUS_CLASSES[status]}`}>
              {status}
            </span>
          );
        },
      },
      {
        header: "Actions",
        render: (t) => (
          <div className="flex space-x-2">
            <IconButton
              icon={faRotate}
              title="Rotate"
              disabled={isTokenInactive(getTokenStatus(t))}
              onClick={() => setRotatingToken(t)}
            />
            <IconButton
              icon={faBan}
              title="Revoke"
              disabled={isTokenInactive(getTokenStatus(t))}
              onClick={() => setRevokingToken(t)}
            />
          </div>
        ),
      },
    ],
    [],
  );

  return (
    <PageContainer title="SCIM">
      <div
        className="mb-4 p-4 rounded-md border
          border-ui-border dark:border-ui-border-dark
          bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark"
      >
        <h3 className="text-sm font-semibold mb-1">Provisioning endpoint</h3>
        <div className="flex items-center gap-2">
          <code className="font-mono text-sm break-all">{scimBaseUrl}</code>
          <IconButton
            icon={faCopy}
            title="Copy provisioning endpoint"
            onClick={handleCopyEndpoint}
          />
        </div>
        <p className="text-xs mt-1 opacity-70">
          Configure your identity provider with this URL and a bearer token
          below.
        </p>
      </div>

      <ScimStatusPanel
        status={status}
        isLoading={isStatusLoading}
        error={statusError}
        onRetry={refreshStatus}
      />

      <PageStatus
        isLoading={isLoading}
        loadingText="Loading SCIM tokens..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mb-4 flex items-center justify-end">
            <Button
              variant="secondary"
              onClick={() => setIsCreateOpen(true)}
              icon={faPlus}
              className="whitespace-nowrap h-8"
            >
              Create token
            </Button>
          </div>

          <EntityListTable data={tokens} columns={columns} searchTerm="" />

          <CreateScimTokenModal
            isOpen={isCreateOpen}
            onClose={() => setIsCreateOpen(false)}
            onCreated={handleCreated}
          />

          <RotateScimTokenModal
            isOpen={!!rotatingToken}
            onClose={() => setRotatingToken(null)}
            onConfirm={() => {
              void handleConfirmRotate();
            }}
            token={rotatingToken}
            isProcessing={isProcessing}
          />

          <RevokeScimTokenModal
            isOpen={!!revokingToken}
            onClose={() => setRevokingToken(null)}
            onConfirm={() => {
              void handleConfirmRevoke();
            }}
            token={revokingToken}
            isProcessing={isProcessing}
          />
        </>
      )}

      <ScimActivityTable
        entries={activity.entries}
        outcome={outcomeFilter}
        onOutcomeChange={setOutcomeFilter}
        isLoading={activity.isLoading}
        isLoadingMore={activity.isLoadingMore}
        hasMore={activity.hasMore}
        error={activity.error}
        onLoadMore={() => {
          void activity.loadMore();
        }}
        onRefresh={() => {
          refreshActivity();
          refreshStatus();
        }}
      />

      {/* Deliberately outside the isLoading/error gate above: creating or rotating a token
          calls refresh() right after this modal is populated, and that refetch flips isLoading
          (or, on failure, sets error). Either would unmount this modal mid-display, and the
          plaintext token shown here can never be retrieved again once that happens. */}
      <ScimTokenSecretModal
        isOpen={!!secretToken}
        onClose={() => setSecretToken(null)}
        token={secretToken}
      />
    </PageContainer>
  );
}
