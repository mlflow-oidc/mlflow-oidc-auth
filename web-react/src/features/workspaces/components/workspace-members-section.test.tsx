import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import WorkspaceMembersSection from "./workspace-members-section";

import type { PermissionLevel } from "../../../shared/types/entity";

const mockShowToast = vi.fn();

vi.mock("../../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

vi.mock("../../../shared/components/page/page-status", () => ({
  default: ({ isLoading, error }: { isLoading: boolean; error: Error | null }) => {
    if (isLoading) return <div>Loading...</div>;
    if (error) return <div>Error</div>;
    return null;
  },
}));

vi.mock("../../../shared/components/modal", () => ({
  Modal: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="modal" title={title}>
      {children}
    </div>
  ),
}));

vi.mock("../../../shared/components/permission-level-select", () => ({
  PermissionLevelSelect: () => <div data-testid="permission-level-select" />,
}));

vi.mock("../../../shared/components/icon-button", () => ({
  IconButton: ({ title, onClick }: { title: string; onClick: () => void }) => (
    <button data-testid={`icon-button-${title}`} onClick={onClick}>
      {title}
    </button>
  ),
}));

vi.mock("../../../shared/components/button", () => ({
  Button: ({ children, onClick, disabled }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean }) => (
    <button onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

const defaultProps = {
  title: "Users",
  members: [] as Array<{ name: string; permission: PermissionLevel }>,
  isLoading: false,
  error: null,
  onUpdate: vi.fn().mockResolvedValue(undefined),
  onRemove: vi.fn().mockResolvedValue(undefined),
  onRefresh: vi.fn(),
  nameLabel: "Username",
};

describe("WorkspaceMembersSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders member list with names and permissions", () => {
    render(
      <WorkspaceMembersSection
        {...defaultProps}
        members={[
          { name: "alice", permission: "MANAGE" },
          { name: "bob", permission: "READ" },
        ]}
      />,
    );

    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("MANAGE")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
    expect(screen.getByText("READ")).toBeInTheDocument();
  });

  it("renders section title with member count", () => {
    render(
      <WorkspaceMembersSection
        {...defaultProps}
        members={[
          { name: "alice", permission: "MANAGE" },
          { name: "bob", permission: "READ" },
        ]}
      />,
    );

    expect(screen.getByText("Users (2)")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    render(<WorkspaceMembersSection {...defaultProps} isLoading={true} />);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<WorkspaceMembersSection {...defaultProps} members={[]} />);

    expect(screen.getByText("No users assigned.")).toBeInTheDocument();
  });

  it("renders edit and remove buttons for each member", () => {
    render(
      <WorkspaceMembersSection
        {...defaultProps}
        members={[
          { name: "alice", permission: "MANAGE" },
          { name: "bob", permission: "READ" },
        ]}
      />,
    );

    const editButtons = screen.getAllByTestId("icon-button-Edit permission");
    const removeButtons = screen.getAllByTestId("icon-button-Remove member");

    expect(editButtons).toHaveLength(2);
    expect(removeButtons).toHaveLength(2);
  });
});
