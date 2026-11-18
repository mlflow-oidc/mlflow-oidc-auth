import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Mock } from "vitest";
import IssueDetectionSchedulesPage from "./issue-detection-schedules-page";
import { reasonLabel } from "./reasons";
import type {
  IssueDetectionSchedule,
  IssueDetectionScheduleCheck,
} from "../../shared/types/entity";

vi.mock("react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router")>()),
  Navigate: (props: { to: string }) => (
    <div data-testid="navigate" data-to={props.to} />
  ),
}));

const mockUseUser: Mock<() => { currentUser: { is_admin: boolean } | null }> =
  vi.fn();
vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser(),
}));

const mockRefresh = vi.fn();
const mockUseSchedules =
  vi.fn<
    typeof import("../../core/hooks/use-issue-detection-schedules").useIssueDetectionSchedules
  >();
vi.mock("../../core/hooks/use-issue-detection-schedules", () => ({
  useIssueDetectionSchedules: () => mockUseSchedules(),
}));

const mockShowToast = vi.fn();
vi.mock("../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

const mockCheck = vi.fn<() => Promise<IssueDetectionScheduleCheck>>();
vi.mock("../../core/services/issue-detection-schedule-service", () => ({
  checkIssueDetectionSchedules: () => mockCheck(),
  fetchIssueDetectionSchedules: vi.fn(),
}));

const base: IssueDetectionSchedule = {
  experiment_id: "1",
  experiment_name: "churn",
  workspace: null,
  readable: true,
  paused: false,
  uses_server_credentials: false,
  model: { endpoint_name: "team-endpoint" },
  author: "alice@example.com",
  recorded_at: "2026-11-18T12:00:00+00:00",
  guard_paused_at: null,
  guard_reason: null,
  violation: null,
};

const SCHEDULES: IssueDetectionSchedule[] = [
  base,
  {
    ...base,
    experiment_id: "2",
    experiment_name: "fraud",
    model: {
      provider: "openai",
      model: "gpt",
      secret_id: "s1",
      secret_name: "team-key",
    },
    author: null,
    violation: "unknown_author",
  },
  {
    ...base,
    experiment_id: "3",
    experiment_name: "ads",
    model: null,
    uses_server_credentials: true,
    paused: true,
    guard_reason: "author_cannot_use_model",
    guard_paused_at: "2026-11-18T13:00:00+00:00",
  },
];

function hookResult(
  overrides: Partial<ReturnType<typeof mockUseSchedules>> = {},
) {
  return {
    schedules: SCHEDULES,
    supported: true,
    guardRunning: true,
    guardIntervalSeconds: 300,
    serverCredentialsAdminOnly: false,
    isLoading: false,
    error: null,
    refresh: mockRefresh,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <IssueDetectionSchedulesPage />
    </MemoryRouter>,
  );
}

describe("IssueDetectionSchedulesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseUser.mockReturnValue({ currentUser: { is_admin: true } });
    mockUseSchedules.mockReturnValue(hookResult());
  });

  it("redirects a non-admin", () => {
    mockUseUser.mockReturnValue({ currentUser: { is_admin: false } });
    renderPage();
    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/403");
  });

  it("lists each schedule with its writer, model and status", () => {
    renderPage();
    expect(screen.getByText("churn")).toBeInTheDocument();
    expect(screen.getAllByText("alice@example.com")).toHaveLength(2);
    expect(screen.getByText("Endpoint team-endpoint")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();

    expect(screen.getByText("openai / gpt (key team-key)")).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.getByText("Will be paused")).toBeInTheDocument();
    expect(screen.getByText(reasonLabel("unknown_author"))).toBeInTheDocument();

    expect(screen.getByText("MLflow default model")).toBeInTheDocument();
    expect(screen.getByText("(server credentials)")).toBeInTheDocument();
    expect(screen.getByText("Paused by guard")).toBeInTheDocument();
  });

  it("says when this MLflow has no recurring detection", () => {
    mockUseSchedules.mockReturnValue(
      hookResult({ supported: false, schedules: [] }),
    );
    renderPage();
    expect(
      screen.getByText(/no recurring issue detection/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Check now")).toBeNull();
  });

  it("says when the automatic check is off", () => {
    mockUseSchedules.mockReturnValue(hookResult({ guardRunning: false }));
    renderPage();
    expect(screen.getByText(/Automatic checks are off/)).toBeInTheDocument();
  });

  it("runs the check, reports what it paused and refreshes", async () => {
    mockCheck.mockResolvedValue({
      checked: 2,
      paused: [
        { experiment_id: "2", workspace: null, reason: "unknown_author" },
      ],
      failed: [],
    });
    renderPage();
    fireEvent.click(screen.getByText("Check now"));
    await waitFor(() =>
      expect(mockShowToast).toHaveBeenCalledWith(
        "Checked 2 running schedule(s); paused 1",
        "success",
      ),
    );
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("reports a failed check", async () => {
    mockCheck.mockRejectedValue(new Error("boom"));
    renderPage();
    fireEvent.click(screen.getByText("Check now"));
    await waitFor(() =>
      expect(mockShowToast).toHaveBeenCalledWith(expect.any(String), "error"),
    );
  });

  it("labels every reason the server can give", () => {
    for (const reason of [
      "unknown_author",
      "model_changed",
      "author_deleted",
      "author_deactivated",
      "author_cannot_update_experiment",
      "author_cannot_use_model",
      "server_credentials_admin_only",
    ]) {
      expect(reasonLabel(reason)).not.toBe(reason);
    }
    expect(reasonLabel("something_new")).toBe("something_new");
    expect(reasonLabel(null)).toBe("");
  });
});
