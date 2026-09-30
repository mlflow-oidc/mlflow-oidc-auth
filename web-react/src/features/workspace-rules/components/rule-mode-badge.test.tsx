import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RuleModeBadge } from "./rule-mode-badge";

describe("RuleModeBadge", () => {
  it("labels a report rule and says it writes nothing", () => {
    render(<RuleModeBadge mode="report" />);
    const badge = screen.getByText("Report");
    expect(badge).toHaveAttribute(
      "title",
      expect.stringContaining("writes nothing"),
    );
    expect(badge.className).toContain("amber");
  });

  it("labels an enforced rule", () => {
    render(<RuleModeBadge mode="enforce" />);
    const badge = screen.getByText("Enforce");
    expect(badge.className).toContain("green");
  });
});
