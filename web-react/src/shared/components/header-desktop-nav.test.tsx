import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import HeaderDesktopNav from "./header-desktop-nav";
import { MemoryRouter } from "react-router";

describe("HeaderDesktopNav", () => {
  const mockMainLinks = [
    { label: "Main 1", href: "/main1", isInternalLink: true },
    { label: "Main 2", href: "/main2", isInternalLink: true },
  ];
  const mockUserControls = [
    { label: "User 1", href: "/user1", isInternalLink: true },
  ];

  it("renders main links and user controls", () => {
    render(
      <MemoryRouter>
        <HeaderDesktopNav
          mainLinks={mockMainLinks}
          userControls={mockUserControls}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Main 1")).toBeInTheDocument();
    expect(screen.getByText("Main 2")).toBeInTheDocument();
    expect(screen.getByText("User 1")).toBeInTheDocument();
  });
});
