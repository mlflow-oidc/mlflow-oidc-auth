import { Button } from "../../../shared/components/button";
import { Select } from "../../../shared/components/select";
import { formatDateTime } from "../../../shared/utils/format-date-time";
import type {
  ScimActivityEntry,
  ScimActivityOutcome,
} from "../../../shared/types/scim";

const OUTCOME_LABELS: Record<ScimActivityOutcome, string> = {
  ok: "OK",
  client_error: "Client error",
  server_error: "Server error",
  auth_failed: "Auth failed",
};

const OUTCOME_OPTIONS = [
  { label: "All outcomes", value: "" },
  ...(Object.keys(OUTCOME_LABELS) as ScimActivityOutcome[]).map((value) => ({
    label: OUTCOME_LABELS[value],
    value,
  })),
];

interface ScimActivityTableProps {
  entries: ScimActivityEntry[];
  outcome: ScimActivityOutcome | null;
  onOutcomeChange: (outcome: ScimActivityOutcome | null) => void;
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  error: Error | null;
  onLoadMore: () => void;
  onRefresh: () => void;
}

const cellClass = "py-2 px-3 align-top";
const headClass = "py-2 px-3 font-medium";

function isError(entry: ScimActivityEntry): boolean {
  return entry.outcome !== "ok";
}

function isOutcome(value: string): value is ScimActivityOutcome {
  return value in OUTCOME_LABELS;
}

/** The most recent `/scim/v2` requests, errors highlighted, filterable by outcome. */
export function ScimActivityTable({
  entries,
  outcome,
  onOutcomeChange,
  isLoading,
  isLoadingMore,
  hasMore,
  error,
  onLoadMore,
  onRefresh,
}: ScimActivityTableProps) {
  return (
    <section aria-label="Recent activity" className="mt-6">
      <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
        <h3 className="text-sm font-semibold">Recent activity</h3>
        <div className="flex items-end gap-2">
          <Select
            id="scim-activity-outcome"
            aria-label="Filter by outcome"
            value={outcome ?? ""}
            options={OUTCOME_OPTIONS}
            onChange={(event) => {
              const value = event.target.value;
              onOutcomeChange(isOutcome(value) ? value : null);
            }}
          />
          <Button variant="ghost" onClick={onRefresh} disabled={isLoading}>
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <p className="mb-2 text-sm text-status-danger dark:text-status-danger-dark">
          Failed to load SCIM activity.
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left text-ui-text dark:text-ui-text-dark">
          <thead>
            <tr className="border-b border-ui-border dark:border-ui-border-dark">
              <th className={headClass}>Time</th>
              <th className={headClass}>Token</th>
              <th className={headClass}>Method</th>
              <th className={headClass}>Resource</th>
              <th className={headClass}>Status</th>
              <th className={headClass}>Outcome</th>
              <th className={headClass}>Error</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr
                key={entry.id}
                data-testid={`scim-activity-${entry.id}`}
                data-error={isError(entry) ? "true" : undefined}
                className={`border-b border-ui-border dark:border-ui-border-dark ${
                  isError(entry)
                    ? "bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-300"
                    : ""
                }`}
              >
                <td className={`${cellClass} whitespace-nowrap`}>{formatDateTime(entry.at)}</td>
                <td className={cellClass}>{entry.token_name ?? <span className="italic">unauthenticated</span>}</td>
                <td className={`${cellClass} font-mono`}>{entry.method}</td>
                <td className={`${cellClass} font-mono break-all`}>
                  {entry.path}
                  {entry.resource_id && (
                    <span className="block text-xs opacity-80">{entry.resource_id}</span>
                  )}
                </td>
                <td className={`${cellClass} font-mono`}>{entry.status}</td>
                <td className={cellClass}>{OUTCOME_LABELS[entry.outcome]}</td>
                <td className={`${cellClass} break-words`}>{entry.error ?? ""}</td>
              </tr>
            ))}
            {!isLoading && entries.length === 0 && (
              <tr>
                <td colSpan={7} className="py-4 px-3 text-center opacity-70">
                  No SCIM activity recorded.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {isLoading && <p className="mt-2 text-sm opacity-70">Loading activity...</p>}

      {hasMore && (
        <div className="mt-3 flex justify-center">
          <Button variant="secondary" onClick={onLoadMore} disabled={isLoadingMore}>
            {isLoadingMore ? "Loading..." : "Load more"}
          </Button>
        </div>
      )}
    </section>
  );
}
