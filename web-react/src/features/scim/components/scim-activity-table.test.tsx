import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ScimActivityTable } from "./scim-activity-table";
import type { ScimActivityEntry } from "../../../shared/types/scim";

const ok: ScimActivityEntry = {
  id: 2,
  at: "2026-09-01T00:00:00+00:00",
  token_id: 1,
  token_name: "entra",
  method: "GET",
  path: "/Users/{user_id}",
  resource_id: "alice@example.com",
  status: 200,
  outcome: "ok",
  error: null,
  duration_ms: 4,
};

const failed: ScimActivityEntry = {
  ...ok,
  id: 1,
  token_id: null,
  token_name: null,
  path: "/Users",
  resource_id: null,
  status: 401,
  outcome: "auth_failed",
  error: "A valid SCIM bearer token is required",
};

function renderTable(overrides: Partial<Parameters<typeof ScimActivityTable>[0]> = {}) {
  const props = {
    entries: [ok, failed],
    outcome: null,
    onOutcomeChange: vi.fn(),
    isLoading: false,
    isLoadingMore: false,
    hasMore: false,
    error: null,
    onLoadMore: vi.fn(),
    onRefresh: vi.fn(),
    ...overrides,
  };
  render(<ScimActivityTable {...props} />);
  return props;
}

describe("ScimActivityTable", () => {
  it("renders rows and highlights errors", () => {
    renderTable();
    const okRow = screen.getByTestId("scim-activity-2");
    const errorRow = screen.getByTestId("scim-activity-1");
    expect(okRow).toHaveTextContent("entra");
    expect(okRow).toHaveTextContent("/Users/{user_id}");
    expect(okRow).toHaveTextContent("alice@example.com");
    expect(okRow).not.toHaveAttribute("data-error");
    expect(errorRow).toHaveAttribute("data-error", "true");
    expect(errorRow).toHaveTextContent("unauthenticated");
    expect(errorRow).toHaveTextContent("Auth failed");
    expect(errorRow).toHaveTextContent("A valid SCIM bearer token is required");
  });

  it("changes the outcome filter", () => {
    const props = renderTable();
    const select = screen.getByLabelText("Filter by outcome");
    fireEvent.change(select, { target: { value: "server_error" } });
    expect(props.onOutcomeChange).toHaveBeenCalledWith("server_error");
    fireEvent.change(select, { target: { value: "" } });
    expect(props.onOutcomeChange).toHaveBeenLastCalledWith(null);
  });

  it("loads more and refreshes", () => {
    const props = renderTable({ hasMore: true });
    fireEvent.click(screen.getByText("Load more"));
    expect(props.onLoadMore).toHaveBeenCalled();
    fireEvent.click(screen.getByText("Refresh"));
    expect(props.onRefresh).toHaveBeenCalled();
  });

  it("hides load more on the last page and shows the empty state", () => {
    renderTable({ entries: [] });
    expect(screen.queryByText("Load more")).not.toBeInTheDocument();
    expect(screen.getByText("No SCIM activity recorded.")).toBeInTheDocument();
  });

  it("shows loading and error messages", () => {
    renderTable({ entries: [], isLoading: true, error: new Error("x"), hasMore: true, isLoadingMore: true });
    expect(screen.getByText("Loading activity...")).toBeInTheDocument();
    expect(screen.getByText("Failed to load SCIM activity.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Loading..." })).toBeDisabled();
  });
});
