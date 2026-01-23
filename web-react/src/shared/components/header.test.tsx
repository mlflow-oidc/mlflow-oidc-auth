import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Header from "./header";
import { MemoryRouter } from "react-router";

// Mock dependencies
vi.mock("../context/use-runtime-config", () => ({
  useRuntimeConfig: () => ({ basePath: "/" }),
}));

vi.mock("./navigation-data", () => ({
  getNavigationData: (userName: string, _basePath: string) => ({
    mainLinks: [
      { to: "/link1", label: "Link 1" },
    ],
    userControls: [
      { to: "/user", label: userName },
    ],
  }),
}));

vi.mock("./dark-mode-toggle", () => ({
  default: () => <button>Dark Mode Toggle</button>,
}));

vi.mock("./header-desktop-nav", () => ({
  default: ({ mainLinks, userControls }: any) => (
    <div data-testid="desktop-nav">
      {mainLinks.map((l: any) => <span key={l.to}>{l.label}</span>)}
      {userControls.map((l: any) => <span key={l.to}>{l.label}</span>)}
    </div>
  ),
}));

vi.mock("./header-mobile-nav", () => ({
  default: ({ isMenuOpen }: any) => <div data-testid="mobile-nav">Open: {String(isMenuOpen)}</div>,
}));

describe("Header", () => {
  it("renders logo and title", () => {
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>
    );
    expect(screen.getByText("Permissions")).toBeInTheDocument();
    expect(screen.getByAltText("Logo")).toBeInTheDocument();
  });

  it("renders desktop nav with correct links", () => {
    render(
      <MemoryRouter>
        <Header userName="TestUser" />
      </MemoryRouter>
    );
    expect(screen.getByTestId("desktop-nav")).toHaveTextContent("Link 1");
    expect(screen.getByTestId("desktop-nav")).toHaveTextContent("TestUser");
  });

  it("toggles mobile menu", () => {
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>
    );

    // Initial state
    expect(screen.getByTestId("mobile-nav")).toHaveTextContent("Open: false");

    // Click toggle button (it has font awesome icon inside generic button)
    // We can find it by aria-expanded attribute
    const toggleBtn = screen.getByRole("button", { expanded: false });
    fireEvent.click(toggleBtn);

    expect(toggleBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("mobile-nav")).toHaveTextContent("Open: true");

    // Click again to close
    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByTestId("mobile-nav")).toHaveTextContent("Open: false");
  });
});
