import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import Sidebar from "./sidebar";
import { MemoryRouter } from "react-router";
import { faHome } from "@fortawesome/free-solid-svg-icons";

// Mock dependencies
vi.mock("./sidebar-data", () => ({
  getSidebarData: (isAdmin: boolean) => [
    { label: "Home", href: "/home", icon: faHome, isInternalLink: true },
    ...(isAdmin ? [{ label: "Admin", href: "/admin", icon: faHome, isInternalLink: true }] : []),
  ],
}));

describe("Sidebar", () => {
  it("renders sidebar items for regular user", () => {
    render(
      <MemoryRouter>
        <Sidebar
          currentUser={{
            username: "user",
            is_admin: false,
            display_name: "User",
            groups: [],
            id: 1,
            is_service_account: false,
            password_expiration: null,
          }}
          isOpen={true}
          toggleSidebar={() => {}}
          widthClass="w-64"
        />
      </MemoryRouter>
    );

    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });

  it("renders admin items for admin user", () => {
    render(
      <MemoryRouter>
        <Sidebar
          currentUser={{
            username: "admin",
            is_admin: true,
            display_name: "Admin",
            groups: [],
            id: 2,
            is_service_account: false,
            password_expiration: null,
          }}
          isOpen={true}
          toggleSidebar={() => {}}
          widthClass="w-64"
        />
      </MemoryRouter>
    );

    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("toggles sidebar on button click", () => {
    const handleToggle = vi.fn();
    render(
      <MemoryRouter>
        <Sidebar
          currentUser={null}
          isOpen={true}
          toggleSidebar={handleToggle}
          widthClass="w-64"
        />
      </MemoryRouter>
    );

    const toggleBtn = screen.getByLabelText("Collapse Sidebar");
    fireEvent.click(toggleBtn);
    expect(handleToggle).toHaveBeenCalled();
  });

  it("renders sponsor link", () => {
    render(
      <MemoryRouter>
        <Sidebar
          currentUser={null}
          isOpen={true}
          toggleSidebar={() => {}}
          widthClass="w-64"
        />
      </MemoryRouter>
    );

    const sponsorLink = screen.getByText("Support the project");
    expect(sponsorLink).toBeInTheDocument();
    expect(sponsorLink.closest("a")).toHaveAttribute(
      "href",
      "https://github.com/sponsors/mlflow-oidc?o=esb"
    );
  });
});
