import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router";
import { RowActionButton } from "./row-action-button";

vi.mock("../context/use-runtime-config", () => ({
  useRuntimeConfig: () => ({ basePath: "/app", uiPath: "/mlflow/oidc/ui" }),
}));

function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

describe("RowActionButton", () => {
  it("renders with text", () => {
    render(
      <MemoryRouter>
        <RowActionButton
          entityId="123"
          route="details"
          buttonText="View Details"
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("View Details")).toBeInTheDocument();
  });

  it("navigates on click", () => {
    const handleUpstreamClick = vi.fn();
    render(
      <MemoryRouter>
        <div onClick={handleUpstreamClick}>
          <RowActionButton entityId="123" route="details" buttonText="View" />
        </div>
        <LocationDisplay />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "View" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/details/123");
    expect(handleUpstreamClick).not.toHaveBeenCalled();
  });

  it("normalizes leading slashes in route", () => {
    render(
      <MemoryRouter
        basename="/mlflow/oidc/ui"
        initialEntries={["/mlflow/oidc/ui"]}
      >
        <RowActionButton
          entityId="456"
          route="/experiments"
          buttonText="Manage permissions"
        />
        <LocationDisplay />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Manage permissions" }));

    expect(screen.getByTestId("location")).toHaveTextContent(
      "/experiments/456",
    );
  });
});
