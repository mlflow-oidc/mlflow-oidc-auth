import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PageStatus from "./page-status";

describe("PageStatus", () => {
  it("renders loading state", () => {
    render(<PageStatus isLoading={true} loadingText="Wait..." />);
    expect(screen.getByText("Wait...")).toBeDefined();
  });

  it("renders default loading state", () => {
    render(<PageStatus isLoading={true} />);
    expect(screen.getByText("Loading...")).toBeDefined();
  });

  it("renders error state with retry button", () => {
    const mockRetry = vi.fn();
    render(
      <PageStatus
        isLoading={false}
        error={new Error("Failed")}
        onRetry={mockRetry}
      />,
    );

    expect(screen.getByText("Error: Failed")).toBeDefined();
    const retryButton = screen.getByText("Try Again");
    fireEvent.click(retryButton);
    expect(mockRetry).toHaveBeenCalled();
  });

  it("returns null when not loading and no error", () => {
    const { container } = render(<PageStatus isLoading={false} />);
    expect(container.firstChild).toBeNull();
  });
});
