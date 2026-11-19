import type { IssueDetectionScheduleList } from "../../shared/types/entity";
import { fetchIssueDetectionSchedules } from "../services/issue-detection-schedule-service";
import { useApi } from "./use-api";

/** The stored issue detection schedules and the schedule guard's settings (admin only). */
export function useIssueDetectionSchedules() {
  const {
    data,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<IssueDetectionScheduleList>(fetchIssueDetectionSchedules);

  return {
    schedules: data?.schedules ?? [],
    supported: data?.supported ?? true,
    guardRunning: data?.guard_running ?? false,
    guardIntervalSeconds: data?.guard_interval_seconds ?? 0,
    serverCredentialsAdminOnly: data?.server_credentials_admin_only ?? false,
    isLoading,
    error,
    refresh,
  };
}
