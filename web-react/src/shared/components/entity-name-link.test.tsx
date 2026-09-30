import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router";
import { EntityNameLink } from "./entity-name-link";

describe("EntityNameLink", () => {
  it("renders a link with the given href and accessible name", () => {
    render(
      <MemoryRouter>
        <EntityNameLink to="/groups/team%2F1" title="team/1">
          team/1
        </EntityNameLink>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "team/1" });
    expect(link).toHaveAttribute("href", "/groups/team%2F1");
    expect(link).toHaveAttribute("title", "team/1");
  });

  it("is keyboard focusable", () => {
    render(
      <MemoryRouter>
        <EntityNameLink to="/experiments/1">Exp 1</EntityNameLink>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "Exp 1" });
    link.focus();
    expect(document.activeElement).toBe(link);
  });

  it("appends extra class names", () => {
    render(
      <MemoryRouter>
        <EntityNameLink to="/users/a" className="opacity-50">
          a
        </EntityNameLink>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "a" })).toHaveClass("opacity-50");
  });
});
