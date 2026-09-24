import { Button } from "../../../shared/components/button";
import { formatDateTime } from "../../../shared/utils/format-date-time";
import type { ScimProvisioningStatus } from "../../../shared/types/scim";

interface ScimStatusPanelProps {
  status: ScimProvisioningStatus | null;
  isLoading: boolean;
  error: Error | null;
  onRetry: () => void;
}

const HEALTH = {
  healthy: {
    label: "Healthy",
    className:
      "bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800",
  },
  unhealthy: {
    label: "Unhealthy",
    className:
      "bg-red-50 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800",
  },
  never: {
    label: "Never used",
    className:
      "bg-gray-50 text-gray-600 border-gray-200 dark:bg-gray-800/50 dark:text-gray-300 dark:border-gray-700",
  },
} as const;

function healthKey(healthy: boolean | null): keyof typeof HEALTH {
  if (healthy === null) return "never";
  return healthy ? "healthy" : "unhealthy";
}

function windowLabel(seconds: number): string {
  if (seconds % 86400 === 0) {
    const days = seconds / 86400;
    return days === 1 ? "24 hours" : `${days} days`;
  }
  if (seconds % 3600 === 0) return `${seconds / 3600} hours`;
  return `${seconds} seconds`;
}

const cellClass = "py-2 px-3 text-ui-text dark:text-ui-text-dark align-top";
const headClass = "py-2 px-3 font-medium text-ui-text dark:text-ui-text-dark";
const dangerClass = "text-status-danger dark:text-status-danger-dark";

/**
 * Whether provisioning is working: overall health, last success and last error, and the same
 * per token. Everything shown is what the server recorded; nothing here is inferred client-side.
 */
export function ScimStatusPanel({
  status,
  isLoading,
  error,
  onRetry,
}: ScimStatusPanelProps) {
  if (isLoading && !status) {
    return (
      <section aria-label="Provisioning status" className="mb-4 text-sm opacity-70">
        Loading provisioning status...
      </section>
    );
  }
  if (error) {
    return (
      <section aria-label="Provisioning status" className="mb-4 flex items-center gap-3 text-sm">
        <span className={dangerClass}>Failed to load provisioning status.</span>
        <Button variant="ghost" onClick={onRetry}>
          Retry
        </Button>
      </section>
    );
  }
  if (!status) return null;

  const health = HEALTH[healthKey(status.provisioning_healthy)];

  return (
    <section
      aria-label="Provisioning status"
      className="mb-4 p-4 rounded-md border border-ui-border dark:border-ui-border-dark bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark"
    >
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <h3 className="text-sm font-semibold">Provisioning status</h3>
        <span
          data-testid="scim-health"
          className={`px-2 py-0.5 text-xs font-medium rounded border ${health.className}`}
        >
          {health.label}
        </span>
        <span className="text-xs opacity-70">
          Healthy means a SCIM request succeeded in the last{" "}
          {windowLabel(status.healthy_window_seconds)}. Activity is kept for{" "}
          {status.retention_days > 0 ? `${status.retention_days} days` : "ever"}.
        </span>
      </div>

      <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm mb-3">
        <div>
          <dt className="opacity-70">Last success</dt>
          <dd>{formatDateTime(status.last_success_at)}</dd>
        </div>
        <div>
          <dt className="opacity-70">Last error</dt>
          <dd className={status.last_error_at ? dangerClass : ""}>
            {formatDateTime(status.last_error_at)}
            {status.last_error && (
              <span className="block text-xs break-words" data-testid="scim-last-error">
                {status.last_error}
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="opacity-70">Requests (24h)</dt>
          <dd>
            {status.requests_24h}
            {status.errors_24h > 0 && (
              <span className={`ml-1 ${dangerClass}`}>
                ({status.errors_24h} failed)
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="opacity-70">Rejected tokens (24h)</dt>
          <dd className={status.auth_failures_24h > 0 ? dangerClass : ""}>
            {status.auth_failures_24h}
            {status.last_auth_failure_at && (
              <span className="block text-xs">
                last {formatDateTime(status.last_auth_failure_at)}
              </span>
            )}
          </dd>
        </div>
      </dl>

      {status.tokens.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left" aria-label="Status per token">
            <thead>
              <tr className="border-b border-ui-border dark:border-ui-border-dark">
                <th className={headClass}>Token</th>
                <th className={headClass}>Last used</th>
                <th className={headClass}>Last success</th>
                <th className={headClass}>Last error</th>
                <th className={headClass}>Requests (24h)</th>
                <th className={headClass}>Errors (24h)</th>
              </tr>
            </thead>
            <tbody>
              {status.tokens.map((token) => (
                <tr
                  key={token.token_id}
                  data-testid={`scim-token-status-${token.token_id}`}
                  className={`border-b border-ui-border dark:border-ui-border-dark ${token.active ? "" : "opacity-50"}`}
                >
                  <td className={cellClass}>
                    {token.name}
                    {!token.active && <span className="ml-1 text-xs">(inactive)</span>}
                  </td>
                  <td className={cellClass}>{formatDateTime(token.last_used_at)}</td>
                  <td className={cellClass}>{formatDateTime(token.last_success_at)}</td>
                  <td className={`${cellClass} ${token.last_error_at ? dangerClass : ""}`}>
                    {formatDateTime(token.last_error_at)}
                    {token.last_error && (
                      <span className="block text-xs break-words">{token.last_error}</span>
                    )}
                  </td>
                  <td className={cellClass}>{token.requests_24h}</td>
                  <td className={`${cellClass} ${token.errors_24h > 0 ? dangerClass : ""}`}>
                    {token.errors_24h}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
