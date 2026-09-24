import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { UserSessionsModal } from "./user-sessions-modal";
import * as hookModule from "../hooks/use-user-sessions";
import * as service from "../services/user-session-service";
import type { UserSession } from "../../../shared/types/user";

const mockShowToast = vi.fn();
const mockRefresh = vi.fn();

vi.mock("../hooks/use-user-sessions");
vi.mock("../services/user-session-service");
vi.mock("../../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

const sessions: UserSession[] = [
  {
    pk: 11,
    session_id_prefix: "abcd1234",
    provider_id: "default",
    created_at: "2026-09-01T00:00:00+00:00",
    last_seen_at: null,
    expires_at: "2026-09-02T00:00:00+00:00",
  },
  {
    pk: 12,
    session_id_prefix: "efgh5678",
    provider_id: null,
    created_at: null,
    last_seen_at: null,
    expires_at: null,
  },
];

function mockSessions(overrides: Partial<ReturnType<typeof hookModule.useUserSessions>> = {}) {
  vi.spyOn(hookModule, "useUserSessions").mockReturnValue({
    sessions,
    isLoading: false,
    error: null,
    refresh: mockRefresh,
    ...overrides,
  });
}

describe("UserSessionsModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    HTMLDialogElement.prototype.showModal = vi.fn();
    HTMLDialogElement.prototype.close = vi.fn();
    mockSessions();
  });

  it("renders nothing without a user", () => {
    const { container } = render(<UserSessionsModal username={null} onClose={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists sessions by prefix only", () => {
    render(<UserSessionsModal username="bob@example.com" onClose={vi.fn()} />);
    expect(screen.getByText("Sessions of bob@example.com")).toBeInTheDocument();
    expect(screen.getByTestId("session-11")).toHaveTextContent("abcd1234…");
    expect(screen.getByTestId("session-11")).toHaveTextContent("default");
    expect(screen.getByTestId("session-12")).toHaveTextContent("efgh5678…");
  });

  it("revokes one session after confirmation, toasts and refreshes", async () => {
    vi.mocked(service.revokeUserSession).mockResolvedValue({ revoked: 1 });
    render(<UserSessionsModal username="bob@example.com" onClose={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("Revoke session abcd1234"));
    expect(service.revokeUserSession).not.toHaveBeenCalled();
    expect(screen.getByRole("alertdialog", { hidden: true })).toHaveTextContent("Revoke session abcd1234… of bob@example.com?");

    fireEvent.click(screen.getByText("Confirm revoke"));
    await waitFor(() => expect(service.revokeUserSession).toHaveBeenCalledWith("bob@example.com", 11));
    await waitFor(() => expect(mockShowToast).toHaveBeenCalledWith("Session abcd1234… revoked", "success"));
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("cancelling a confirmation revokes nothing", () => {
    render(<UserSessionsModal username="bob@example.com" onClose={vi.fn()} />);
    fireEvent.click(screen.getByLabelText("Revoke session abcd1234"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByRole("alertdialog", { hidden: true })).not.toBeInTheDocument();
    expect(service.revokeUserSession).not.toHaveBeenCalled();
  });

  it("revokes all after confirmation", async () => {
    vi.mocked(service.revokeAllUserSessions).mockResolvedValue({ revoked: 2 });
    render(<UserSessionsModal username="bob@example.com" onClose={vi.fn()} />);

    fireEvent.click(screen.getByText("Revoke all"));
    expect(screen.getByRole("alertdialog", { hidden: true })).toHaveTextContent("Revoke all 2 sessions of bob@example.com?");
    fireEvent.click(screen.getByText("Confirm revoke"));

    await waitFor(() => expect(service.revokeAllUserSessions).toHaveBeenCalledWith("bob@example.com"));
    await waitFor(() => expect(mockShowToast).toHaveBeenCalledWith("2 sessions of bob@example.com revoked", "success"));
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("toasts an error and still refreshes when revocation fails", async () => {
    vi.mocked(service.revokeUserSession).mockRejectedValue(new Error('HTTP 404: {"detail": "Session not found"}'));
    render(<UserSessionsModal username="bob@example.com" onClose={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("Revoke session efgh5678"));
    fireEvent.click(screen.getByText("Confirm revoke"));

    await waitFor(() => expect(mockShowToast).toHaveBeenCalledWith("Session not found", "error"));
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("disables Revoke all without sessions and shows the empty state", () => {
    mockSessions({ sessions: [] });
    render(<UserSessionsModal username="bob@example.com" onClose={vi.fn()} />);
    expect(screen.getByText("No live sessions.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revoke all", hidden: true })).toBeDisabled();
  });

  it("shows loading and error states", () => {
    mockSessions({ sessions: [], isLoading: true });
    const { rerender } = render(<UserSessionsModal username="bob@example.com" onClose={vi.fn()} />);
    expect(screen.getByText("Loading sessions...")).toBeInTheDocument();

    mockSessions({ sessions: [], error: new Error("boom") });
    rerender(<UserSessionsModal username="bob@example.com" onClose={vi.fn()} />);
    expect(screen.getByText("Failed to load sessions")).toBeInTheDocument();
  });

  it("close calls onClose", () => {
    const onClose = vi.fn();
    render(<UserSessionsModal username="bob@example.com" onClose={onClose} />);
    fireEvent.click(screen.getByText("Close"));
    expect(onClose).toHaveBeenCalled();
  });
});
