import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import AiModelsPage from "./ai-models-page";

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

describe("AiModelsPage", () => {
  it("renders correctly", () => {
    render(<AiModelsPage />);
    expect(screen.getByText("AI Models placeholder")).toBeInTheDocument();
  });

  it("passes correct title to PageContainer", () => {
    render(<AiModelsPage />);
    expect(screen.getByTestId("page-container")).toHaveAttribute(
      "title",
      "AI Models",
    );
  });
});
