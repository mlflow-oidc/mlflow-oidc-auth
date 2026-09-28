import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ScimStatusPanel } from "./scim-status-panel";
import type { ScimProvisioningStatus } from "../../../shared/types/scim";

const base: ScimProvisioningStatus = {
  provisioning_healthy: true,
  last_success_at: "2026-09-01T00:00:00+00:00",
  last_error_at: "2026-09-01T01:00:00+00:00",
  last_error: "uniqueness: User alice already exists",
  requests_24h: 10,
  errors_24h: 2,
  auth_failures_24h: 1,
  last_auth_failure_at: "2026-09-01T02:00:00+00:00",
  healthy_window_seconds: 86400,
  retention_days: 30,
  tokens: [
    {
      token_id: 1,
      name: "entra",
      active: true,
      last_used_at: "2026-09-01T01:00:00+00:00",
      last_success_at: "2026-09-01T00:00:00+00:00",
      last_error_at: "2026-09-01T01:00:00+00:00",
      last_error: "uniqueness: User alice already exists",
      last_error_status: 409,
      requests_24h: 10,
      errors_24h: 2,
    },
    {
      token_id: 2,
      name: "old",
      active: false,
      last_used_at: null,
      last_success_at: null,
      last_error_at: null,
      last_error: null,
      last_error_status: null,
      requests_24h: 0,
      errors_24h: 0,
    },
  ],
};

describe("ScimStatusPanel", () => {
  it("shows healthy, the last error message and per-token status", () => {
    render(<ScimStatusPanel status={base} isLoading={false} error={null} onRetry={vi.fn()} />);
    expect(screen.getByTestId("scim-health")).toHaveTextContent("Healthy");
    expect(screen.getByTestId("scim-last-error")).toHaveTextContent(
      "uniqueness: User alice already exists",
    );
    expect(screen.getByText("(2 failed)")).toBeInTheDocument();
    expect(screen.getByText(/succeeded in the last 24 hours/)).toBeInTheDocument();
    const entra = screen.getByTestId("scim-token-status-1");
    expect(within(entra).getByText("entra")).toBeInTheDocument();
    expect(within(entra).getByText("uniqueness: User alice already exists")).toBeInTheDocument();
    expect(screen.getByTestId("scim-token-status-2")).toHaveTextContent("(inactive)");
  });

  it("shows unhealthy", () => {
    render(
      <ScimStatusPanel
        status={{ ...base, provisioning_healthy: false }}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByTestId("scim-health")).toHaveTextContent("Unhealthy");
  });

  it("shows never used, without a last error", () => {
    render(
      <ScimStatusPanel
        status={{
          ...base,
          provisioning_healthy: null,
          last_error: null,
          last_error_at: null,
          last_success_at: null,
          errors_24h: 0,
          tokens: [],
          healthy_window_seconds: 7200,
          retention_days: 0,
        }}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByTestId("scim-health")).toHaveTextContent("Never used");
    expect(screen.queryByTestId("scim-last-error")).not.toBeInTheDocument();
    expect(screen.getByText(/last 2 hours/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders loading and error states", () => {
    const onRetry = vi.fn();
    const { rerender } = render(
      <ScimStatusPanel status={null} isLoading error={null} onRetry={onRetry} />,
    );
    expect(screen.getByText("Loading provisioning status...")).toBeInTheDocument();

    rerender(
      <ScimStatusPanel status={null} isLoading={false} error={new Error("x")} onRetry={onRetry} />,
    );
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders nothing without data", () => {
    const { container } = render(
      <ScimStatusPanel status={null} isLoading={false} error={null} onRetry={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
