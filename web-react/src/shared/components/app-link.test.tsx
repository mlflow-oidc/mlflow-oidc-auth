import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AppLink } from "./app-link";
import { MemoryRouter } from "react-router";

describe("AppLink", () => {
  it("renders internal link using React Router Link", () => {
    render(
      <MemoryRouter>
        <AppLink href="/internal" isInternalLink>
          Internal Link
        </AppLink>
      </MemoryRouter>
    );

    const link = screen.getByRole("link", { name: "Internal Link" });
    expect(link).toHaveAttribute("href", "/internal");
    // React Router's Link renders as an anchor tag, but handles navigation internally.
    // We can check if it doesn't have target="_blank" which external links have.
    expect(link).not.toHaveAttribute("target");
  });

  it("renders external link as anchor tag with correct attributes", () => {
    render(
      <AppLink href="https://example.com">
        External Link
      </AppLink>
    );

    const link = screen.getByRole("link", { name: "External Link" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders non-http external link (e.g. mailto) without external props if logic dictates, but current logic checks http/s", () => {
    // Current logic: startsWith("http") || startsWith("https") -> isExternal
    // Let's test a simple relative link that is NOT marked as internal.
    // The component defaults to <a> tag if !isInternalLink.
    // isExternalLink checks using http/https.

    render(
      <AppLink href="/relative">
        Relative Link
      </AppLink>
    );

    const link = screen.getByRole("link", { name: "Relative Link" });
    expect(link).toHaveAttribute("href", "/relative");
    // Should NOT have target blank because it doesn't start with http/s
    expect(link).not.toHaveAttribute("target");
  });

  it("calls onClick handler", () => {
    const handleClick = vi.fn();
    render(
      <MemoryRouter>
        <AppLink href="/test" onClick={handleClick}>
          Click Me
        </AppLink>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("link", { name: "Click Me" }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("applies className", () => {
    render(
      <MemoryRouter>
        <AppLink href="/test" className="custom-class">
          Styled Link
        </AppLink>
      </MemoryRouter>
    );

    expect(screen.getByRole("link", { name: "Styled Link" })).toHaveClass("custom-class");
  });
});
