import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import AiSecretsPage from "./ai-secrets-page";

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

describe("AiSecretsPage", () => {
  it("renders correctly", () => {
    render(<AiSecretsPage />);
    expect(screen.getByText("AI Secrets placeholder")).toBeInTheDocument();
  });

  it("passes correct title to PageContainer", () => {
    render(<AiSecretsPage />);
    expect(screen.getByTestId("page-container")).toHaveAttribute(
      "title",
      "AI Secrets",
    );
  });
});
