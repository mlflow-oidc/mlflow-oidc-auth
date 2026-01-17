import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import WebhooksPage from "./webhooks-page";

describe("WebhooksPage", () => {
  it("renders placeholder correctly", () => {
    render(<WebhooksPage />);
    expect(screen.getByText("Placeholder for Webhooks Page")).toBeInTheDocument();
  });
});
