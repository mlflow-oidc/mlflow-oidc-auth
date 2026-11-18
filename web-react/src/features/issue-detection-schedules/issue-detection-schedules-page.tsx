import { useCallback, useState } from "react";
import { Navigate } from "react-router";
import { faShieldHalved } from "@fortawesome/free-solid-svg-icons";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { Button } from "../../shared/components/button";
import { useToast } from "../../shared/components/toast/use-toast";
import { useUser } from "../../core/hooks/use-user";
import { useIssueDetectionSchedules } from "../../core/hooks/use-issue-detection-schedules";
import { checkIssueDetectionSchedules } from "../../core/services/issue-detection-schedule-service";
import { extractErrorMessage } from "../../core/services/http";
import { formatDateTime } from "../../shared/utils/format-date-time";
import type { IssueDetectionSchedule } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import { reasonLabel } from "./reasons";

type Row = IssueDetectionSchedule & { id: string };

function modelLabel(schedule: IssueDetectionSchedule): string {
  const model = schedule.model;
  if (!model) return "MLflow default model";
  if (model.endpoint_name) return `Endpoint ${model.endpoint_name}`;
  const name = [model.provider, model.model].filter(Boolean).join(" / ");
  if (model.secret_id) {
    return `${name} (key ${model.secret_name ?? model.secret_id})`;
  }
  return name || "Unreadable model";
}

function StatusBadge({ schedule }: { schedule: IssueDetectionSchedule }) {
  const base =
    "inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium border whitespace-nowrap";
  if (!schedule.readable) {
    return (
      <span
        className={`${base} bg-gray-50 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700`}
        title="MLflow's scheduler does not read this value as a schedule"
      >
        Ignored by MLflow
      </span>
    );
  }
  if (schedule.paused && schedule.guard_reason) {
    return (
      <span
        className={`${base} bg-red-50 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800`}
        title={reasonLabel(schedule.guard_reason)}
      >
        Paused by guard
      </span>
    );
  }
  if (schedule.paused) {
    return (
      <span
        className={`${base} bg-gray-50 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700`}
      >
        Paused
      </span>
    );
  }
  if (schedule.violation === "check_failed") {
    return (
      <span
        className={`${base} bg-gray-50 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700`}
        title={reasonLabel(schedule.violation)}
      >
        Check failed
      </span>
    );
  }
  if (schedule.violation) {
    return (
      <span
        className={`${base} bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800`}
        title={reasonLabel(schedule.violation)}
      >
        Will be paused
      </span>
    );
  }
  return (
    <span
      className={`${base} bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800`}
    >
      Running
    </span>
  );
}

/**
 * Admin page for MLflow 3.18 recurring issue detection. MLflow runs a stored schedule with no
 * identity, so the plugin records who wrote each one and pauses a schedule whose writer could no
 * longer write it. The server is the authority: every endpoint is admin-only, so this gating is
 * cosmetic.
 */
export default function IssueDetectionSchedulesPage() {
  const { currentUser } = useUser();
  if (currentUser && !currentUser.is_admin)
    return <Navigate to="/403" replace />;
  return <IssueDetectionSchedulesList />;
}

function IssueDetectionSchedulesList() {
  const {
    schedules,
    supported,
    guardRunning,
    guardIntervalSeconds,
    serverCredentialsAdminOnly,
    isLoading,
    error,
    refresh,
  } = useIssueDetectionSchedules();
  const { showToast } = useToast();
  const [isChecking, setIsChecking] = useState(false);

  const handleCheck = useCallback(async () => {
    setIsChecking(true);
    try {
      const result = await checkIssueDetectionSchedules();
      const failed = result.failed.length
        ? `, ${result.failed.length} could not be checked`
        : "";
      showToast(
        `Checked ${result.checked} running schedule(s); paused ${result.paused.length}${failed}`,
        result.failed.length ? "error" : "success",
      );
      refresh();
    } catch (err) {
      showToast(
        extractErrorMessage(err, "Failed to check issue detection schedules"),
        "error",
      );
    } finally {
      setIsChecking(false);
    }
  }, [refresh, showToast]);

  const rows: Row[] = schedules.map((s) => ({ ...s, id: s.experiment_id }));

  const columns: ColumnConfig<Row>[] = [
    {
      header: "Experiment",
      render: (s) => (
        <span
          className="truncate block"
          title={`${s.experiment_name} (${s.experiment_id})`}
        >
          {s.experiment_name}
        </span>
      ),
    },
    ...(schedules.some((s) => s.workspace)
      ? [
          {
            header: "Workspace",
            render: (s: Row) => s.workspace ?? "",
          },
        ]
      : []),
    {
      header: "Model",
      render: (s) => (
        <span className="truncate block" title={modelLabel(s)}>
          {modelLabel(s)}
          {s.uses_server_credentials && (
            <span className="ml-1 text-ui-text-muted dark:text-ui-text-muted-dark">
              (server credentials)
            </span>
          )}
        </span>
      ),
    },
    {
      header: "Written by",
      render: (s) => (
        <span title={s.recorded_at ? formatDateTime(s.recorded_at) : ""}>
          {s.author ?? "Unknown"}
        </span>
      ),
    },
    {
      header: "Status",
      render: (s) => <StatusBadge schedule={s} />,
    },
    {
      header: "Reason",
      render: (s) => {
        const reason = s.paused ? s.guard_reason : s.violation;
        return (
          <span className="truncate block" title={reasonLabel(reason)}>
            {reasonLabel(reason)}
            {s.paused && s.guard_paused_at
              ? ` (${formatDateTime(s.guard_paused_at)})`
              : ""}
          </span>
        );
      },
    },
  ];

  return (
    <PageContainer title="Issue detection schedules">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading issue detection schedules..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && !supported && (
        <p className="text-sm text-ui-text-muted dark:text-ui-text-muted-dark">
          This MLflow server has no recurring issue detection (it arrived in
          MLflow 3.18).
        </p>
      )}

      {!isLoading && !error && supported && (
        <>
          <div className="mb-2 flex items-center justify-between gap-6">
            <p className="text-sm text-ui-text-muted dark:text-ui-text-muted-dark">
              MLflow runs a saved schedule without anyone signed in. A schedule
              is paused when the person who saved it can no longer edit the
              experiment or use the endpoint or key it runs on.{" "}
              {guardRunning
                ? `Checked automatically every ${guardIntervalSeconds} seconds and after permission changes.`
                : "Automatic checks are off on this server; use Check now."}{" "}
              {serverCredentialsAdminOnly
                ? "Only administrators may run detection on the server's own credentials."
                : ""}
            </p>
            <Button
              variant="secondary"
              onClick={() => void handleCheck()}
              icon={faShieldHalved}
              disabled={isChecking}
              className="whitespace-nowrap h-8 mb-1 mt-2"
            >
              {isChecking ? "Checking..." : "Check now"}
            </Button>
          </div>

          <EntityListTable data={rows} columns={columns} searchTerm="" />
        </>
      )}
    </PageContainer>
  );
}
