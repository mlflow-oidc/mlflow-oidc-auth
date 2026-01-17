import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { RowActionButton } from "./row-action-button";

const mockNavigate = vi.fn();

vi.mock("react-router", () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock("../context/use-runtime-config", () => ({
  useRuntimeConfig: () => ({ basePath: "/app" }),
}));

describe("RowActionButton", () => {
  it("renders with text", () => {
    render(
      <RowActionButton
        entityId="123"
        route="details"
        buttonText="View Details"
      />
    );
    expect(screen.getByText("View Details")).toBeInTheDocument();
  });

  it("navigates on click", () => {
    render(
      <RowActionButton
        entityId="123"
        route="details"
        buttonText="View"
      />
    );
    
    // It stops propagation
    const handleUpstreamClick = vi.fn();
    render(
      <div onClick={handleUpstreamClick}>
         <RowActionButton
          entityId="123"
          route="details"
          buttonText="View"
        />
      </div>
    );
    
    // Find button
    const buttons = screen.getAllByRole("button");
    const button = buttons[buttons.length - 1]; // get the last rendered one, or specifically key them
    
    fireEvent.click(button);
    expect(mockNavigate).toHaveBeenCalledWith("/app/details/123");
    expect(handleUpstreamClick).not.toHaveBeenCalled();
  });
});
