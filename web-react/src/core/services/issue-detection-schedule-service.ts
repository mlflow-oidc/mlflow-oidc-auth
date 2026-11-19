import { request } from "./api-utils";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";
import type {
  IssueDetectionScheduleCheck,
  IssueDetectionScheduleList,
} from "../../shared/types/entity";

/** Every stored issue detection schedule, with its recorded writer (admin only). */
export const fetchIssueDetectionSchedules = async (signal?: AbortSignal) =>
  request<IssueDetectionScheduleList>(
    STATIC_API_ENDPOINTS.ISSUE_DETECTION_SCHEDULES,
    { signal },
  );

/** Run the schedule guard's check now; pauses every schedule that may not keep running. */
export const checkIssueDetectionSchedules = async () =>
  request<IssueDetectionScheduleCheck>(
    STATIC_API_ENDPOINTS.ISSUE_DETECTION_SCHEDULES_CHECK,
    { method: "POST" },
  );
