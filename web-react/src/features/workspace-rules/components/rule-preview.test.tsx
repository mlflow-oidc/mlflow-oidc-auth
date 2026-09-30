import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RulePreview } from "./rule-preview";

describe("RulePreview", () => {
  it("says so when nothing matches", () => {
    render(<RulePreview changes={[]} />);
    expect(screen.getByTestId("rule-preview-empty")).toBeInTheDocument();
  });

  it("shows an update as previous → new", () => {
    render(
      <RulePreview
        changes={[
          {
            action: "update",
            group: "team-acme",
            workspace: "acme",
            permission: "EDIT",
            reason: null,
            previous: "READ",
            applied: false,
          },
        ]}
      />,
    );
    expect(screen.getByText("READ → EDIT")).toBeInTheDocument();
    expect(screen.getByText("Update")).toBeInTheDocument();
  });

  it("renders directory-supplied names as text, never as HTML", () => {
    const hostile = '<img src=x onerror="alert(1)">';
    const { container } = render(
      <RulePreview
        changes={[
          {
            action: "grant",
            group: hostile,
            workspace: "acme",
            permission: "READ",
            reason: hostile,
            previous: null,
            applied: false,
          },
        ]}
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getAllByText(hostile)).toHaveLength(2);
  });
});
