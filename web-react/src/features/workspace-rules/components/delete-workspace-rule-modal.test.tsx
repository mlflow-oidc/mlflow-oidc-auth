import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DeleteWorkspaceRuleModal } from "./delete-workspace-rule-modal";
import type { WorkspaceRule } from "../../../shared/types/entity";

const RULE: WorkspaceRule = {
  id: 3,
  name: "tenants",
  pattern: "^team-(?P<ws>[a-z]+)$",
  permission: "EDIT",
  mode: "enforce",
  enabled: true,
  created_by: null,
  created_at: "2026-09-30T12:00:00+00:00",
  updated_at: "2026-09-30T12:00:00+00:00",
};

describe("DeleteWorkspaceRuleModal", () => {
  it("renders nothing without a rule", () => {
    const { container } = render(
      <DeleteWorkspaceRuleModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        rule={null}
        isProcessing={false}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("names the rule and says manual grants stay", () => {
    render(
      <DeleteWorkspaceRuleModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        rule={RULE}
        isProcessing={false}
      />,
    );
    expect(screen.getByText("Delete Workspace Rule")).toBeInTheDocument();
    expect(screen.getByText("tenants")).toBeInTheDocument();
    expect(screen.getByText("^team-(?P<ws>[a-z]+)$")).toBeInTheDocument();
    expect(screen.getByText(/Grants made by hand stay/)).toBeInTheDocument();
  });

  it("confirms and cancels", () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <DeleteWorkspaceRuleModal
        isOpen={true}
        onClose={onClose}
        onConfirm={onConfirm}
        rule={RULE}
        isProcessing={false}
      />,
    );
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Delete Permanently"));
    expect(onConfirm).toHaveBeenCalled();
  });

  it("disables both buttons while deleting", () => {
    render(
      <DeleteWorkspaceRuleModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        rule={RULE}
        isProcessing={true}
      />,
    );
    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });
});
