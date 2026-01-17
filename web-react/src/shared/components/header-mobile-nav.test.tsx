import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import HeaderMobileNav from "./header-mobile-nav";
import { MemoryRouter } from "react-router";

describe("HeaderMobileNav", () => {
  const mockMainLinks = [
    { label: "Main 1", href: "/main1", isInternalLink: true },
  ];
  const mockUserControls = [
    { label: "User 1", href: "/user1", isInternalLink: true },
  ];

  it("renders with links", () => {
    render(
      <MemoryRouter>
        <HeaderMobileNav
          isMenuOpen={true}
          onLinkClick={() => {}}
          mainLinks={mockMainLinks}
          userControls={mockUserControls}
        />
      </MemoryRouter>
    );

    expect(screen.getByText("Main 1")).toBeInTheDocument();
    expect(screen.getByText("User 1")).toBeInTheDocument();
  });

  it("calls onLinkClick when link is clicked", () => {
    const handleLinkClick = vi.fn();
    render(
      <MemoryRouter>
        <HeaderMobileNav
          isMenuOpen={true}
          onLinkClick={handleLinkClick}
          mainLinks={mockMainLinks}
          userControls={mockUserControls}
        />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByText("Main 1"));
    expect(handleLinkClick).toHaveBeenCalled();
  });

  it("applies translate class based on isMenuOpen", () => {
    const { rerender } = render(
      <MemoryRouter>
        <HeaderMobileNav
          isMenuOpen={true}
          onLinkClick={() => {}}
          mainLinks={mockMainLinks}
          userControls={mockUserControls}
        />
      </MemoryRouter>
    );
    // Use container query or check class
    // id="mobile-menu"
    const menu = document.getElementById("mobile-menu");
    expect(menu).toHaveClass("translate-x-0");

    rerender(
      <MemoryRouter>
        <HeaderMobileNav
          isMenuOpen={false}
          onLinkClick={() => {}}
          mainLinks={mockMainLinks}
          userControls={mockUserControls}
        />
      </MemoryRouter>
    );
    expect(menu).toHaveClass("translate-x-full");
  });
});
