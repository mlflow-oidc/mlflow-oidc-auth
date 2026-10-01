import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GrantWorkspaceNotice } from "./grant-workspace-notice";

const SCOPED_IN_TEAM_A = { scoped: true, workspace: "team-a", canChange: true };
const SCOPED_ALL = { scoped: true, workspace: null, canChange: false };

describe("GrantWorkspaceNotice", () => {
  it("names the workspace and offers switching to change another's grants", () => {
    render(<GrantWorkspaceNotice scope={SCOPED_IN_TEAM_A} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Grants shown here belong to workspace team-a. Switch workspaces in the header to see or change another workspace's grants.",
    );
  });

  it("under All Workspaces, says these are default's grants and how to change them", () => {
    render(<GrantWorkspaceNotice scope={SCOPED_ALL} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "These are the default workspace's grants.",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "add, change or remove grants",
    );
  });

  it("on a read-only page, never mentions changing grants", () => {
    const { unmount } = render(
      <GrantWorkspaceNotice scope={SCOPED_IN_TEAM_A} readOnly />,
    );
    expect(screen.getByRole("status")).not.toHaveTextContent(/change/);
    unmount();

    render(<GrantWorkspaceNotice scope={SCOPED_ALL} readOnly />);
    expect(screen.getByRole("status")).toHaveTextContent("to see its grants");
    expect(screen.getByRole("status")).not.toHaveTextContent(/change/);
  });

  it("renders nothing for unscoped grants", () => {
    const { container } = render(
      <GrantWorkspaceNotice
        scope={{ scoped: false, workspace: null, canChange: true }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
