import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import AiEndpointsPage from "./ai-endpoints-page";

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({
    children,
    title,
  }: {
    children: React.ReactNode;
    title: string;
  }) => (
    <div data-testid="page-container" title={title}>
      {children}
    </div>
  ),
}));

describe("AiEndpointsPage", () => {
  it("renders correctly", () => {
    render(<AiEndpointsPage />);
    expect(screen.getByText("AI Endpoints placeholder")).toBeInTheDocument();
  });

  it("passes correct title to PageContainer", () => {
    render(<AiEndpointsPage />);
    expect(screen.getByTestId("page-container")).toHaveAttribute(
      "title",
      "AI Endpoints",
    );
  });
});
