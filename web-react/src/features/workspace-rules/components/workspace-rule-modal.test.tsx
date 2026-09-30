import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { WorkspaceRuleModal } from "./workspace-rule-modal";
import type {
  WorkspaceRule,
  WorkspaceRulePlan,
} from "../../../shared/types/entity";

const mockShowToast = vi.fn();
vi.mock("../../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

type Service = typeof import("../../../core/services/workspace-rule-service");

const mockCreate = vi.fn<Service["createWorkspaceRule"]>();
const mockUpdate = vi.fn<Service["updateWorkspaceRule"]>();
const mockPreview = vi.fn<Service["previewWorkspaceRule"]>();
const mockPreviewUnsaved = vi.fn<Service["previewUnsavedWorkspaceRule"]>();
vi.mock("../../../core/services/workspace-rule-service", () => ({
  createWorkspaceRule: (...args: Parameters<Service["createWorkspaceRule"]>) =>
    mockCreate(...args),
  updateWorkspaceRule: (...args: Parameters<Service["updateWorkspaceRule"]>) =>
    mockUpdate(...args),
  previewWorkspaceRule: (
    ...args: Parameters<Service["previewWorkspaceRule"]>
  ) => mockPreview(...args),
  previewUnsavedWorkspaceRule: (
    ...args: Parameters<Service["previewUnsavedWorkspaceRule"]>
  ) => mockPreviewUnsaved(...args),
  deleteWorkspaceRule: vi.fn(),
}));

const RULE: WorkspaceRule = {
  id: 7,
  name: "tenants",
  pattern: "^team-(?P<ws>[a-z]+)$",
  permission: "READ",
  mode: "report",
  enabled: true,
  created_by: "admin@example.com",
  created_at: "2026-09-30T12:00:00+00:00",
  updated_at: "2026-09-30T12:00:00+00:00",
};

const PLAN: WorkspaceRulePlan = {
  rule: null,
  changes: [
    {
      action: "grant",
      group: "team-acme",
      workspace: "acme",
      permission: "READ",
      reason: null,
      previous: null,
      applied: false,
      rule_id: 1,
    },
    {
      action: "skip",
      group: "team-beta",
      workspace: "beta",
      permission: "READ",
      reason: "manual grant",
      previous: null,
      applied: false,
      rule_id: 1,
    },
    {
      action: "shadowed",
      group: "team-gamma",
      workspace: "gamma",
      permission: "READ",
      reason: "rule 1 (older) wins",
      previous: null,
      applied: false,
      rule_id: 1,
    },
  ],
};

function renderModal(
  props: Partial<React.ComponentProps<typeof WorkspaceRuleModal>> = {},
) {
  const onClose = vi.fn();
  const onSuccess = vi.fn();
  render(
    <WorkspaceRuleModal
      isOpen={true}
      onClose={onClose}
      onSuccess={onSuccess}
      rule={null}
      allowedPermissions={["READ", "USE", "EDIT"]}
      maxPermission="EDIT"
      {...props}
    />,
  );
  return { onClose, onSuccess };
}

function fill(label: string, value: string) {
  // Required fields carry a "*" after their label.
  fireEvent.change(screen.getByLabelText(new RegExp(`^${label}\\*?$`)), {
    target: { value },
  });
}

describe("WorkspaceRuleModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a rule after previewing it", async () => {
    mockPreviewUnsaved.mockResolvedValue(PLAN);
    mockCreate.mockResolvedValue({ rule: { ...RULE }, changes: PLAN.changes });
    const { onClose, onSuccess } = renderModal();

    fill("Name", " tenants ");
    fill("Group name pattern", "^team-(?P<ws>[a-z]+)$");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    const table = await screen.findByRole("table", { name: "Rule preview" });
    expect(mockPreviewUnsaved).toHaveBeenCalledWith({
      pattern: "^team-(?P<ws>[a-z]+)$",
      permission: "READ",
    });
    expect(within(table).getByText("team-acme")).toBeInTheDocument();
    expect(within(table).getByText("Grant")).toBeInTheDocument();
    expect(within(table).getByText("manual grant")).toBeInTheDocument();
    expect(within(table).getByText("Shadowed")).toBeInTheDocument();
    expect(within(table).getByText("rule 1 (older) wins")).toBeInTheDocument();
    expect(screen.getByText(/nothing has been written/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith({
        name: "tenants",
        pattern: "^team-(?P<ws>[a-z]+)$",
        permission: "READ",
        mode: "report",
        enabled: true,
      }),
    );
    expect(onSuccess).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("clears a preview when the pattern changes", async () => {
    mockPreviewUnsaved.mockResolvedValue(PLAN);
    renderModal();

    fill("Group name pattern", "^team-(?P<ws>[a-z]+)$");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByRole("table", { name: "Rule preview" });

    fill("Group name pattern", "^squad-(?P<ws>[a-z]+)$");

    expect(screen.queryByRole("table", { name: "Rule preview" })).toBeNull();
  });

  it("shows the server's 400 message for a pattern without the ws group", async () => {
    const detail =
      "pattern must contain the named group (?P<ws>...) matching the workspace name";
    mockCreate.mockRejectedValue(
      new Error(`HTTP 400: ${JSON.stringify({ detail })}`),
    );
    const { onClose, onSuccess } = renderModal();

    fill("Name", "tenants");
    fill("Group name pattern", "^team-([a-z]+)$");
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
    expect(onSuccess).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("offers only the permissions the server's ceiling allows", () => {
    renderModal({ allowedPermissions: ["READ", "USE"], maxPermission: "USE" });

    const select = screen.getByLabelText<HTMLSelectElement>("Permission");
    const options = Array.from(select.options).map((o) => o.value);
    expect(options).toEqual(["READ", "USE"]);
    expect(options).not.toContain("EDIT");
    expect(options).not.toContain("MANAGE");
    expect(options).not.toContain("NO_PERMISSIONS");
    expect(screen.getByText(/allows rules up to USE/)).toBeInTheDocument();
  });

  it("keeps an existing permission above a lowered ceiling visible, and does not re-send it", async () => {
    mockUpdate.mockResolvedValue({ rule: RULE, changes: [] });
    renderModal({
      rule: { ...RULE, permission: "EDIT" },
      allowedPermissions: ["READ"],
      maxPermission: "READ",
    });

    const select = screen.getByLabelText<HTMLSelectElement>("Permission");
    expect(select.value).toBe("EDIT");
    expect(
      screen.getByText("EDIT (above the READ ceiling)"),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Mode"), {
      target: { value: "enforce" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith(7, { mode: "enforce" }),
    );
  });

  it("edits send only the changed fields", async () => {
    mockUpdate.mockResolvedValue({ rule: RULE, changes: [] });
    renderModal({ rule: RULE });

    expect(screen.getByLabelText("Name*")).toHaveValue("tenants");
    fireEvent.click(screen.getByRole("switch"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith(7, { enabled: false }),
    );
  });

  it("previews a saved rule by id while its pattern and permission are unchanged", async () => {
    mockPreview.mockResolvedValue(PLAN);
    mockPreviewUnsaved.mockResolvedValue(PLAN);
    renderModal({ rule: RULE });

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await screen.findByRole("table", { name: "Rule preview" });
    expect(mockPreview).toHaveBeenCalledWith(7);
    expect(mockPreviewUnsaved).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Permission"), {
      target: { value: "USE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() =>
      expect(mockPreviewUnsaved).toHaveBeenCalledWith({
        pattern: RULE.pattern,
        permission: "USE",
        rule_id: 7,
      }),
    );
  });

  it("requires a name that is not only whitespace", () => {
    renderModal();

    fill("Name", "   ");
    fill("Group name pattern", "^team-(?P<ws>[a-z]+)$");
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(screen.getByText("Name is required")).toBeInTheDocument();
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("ignores a preview that lands after the pattern changed", async () => {
    let resolveSlow: (plan: WorkspaceRulePlan) => void = () => undefined;
    mockPreviewUnsaved.mockImplementationOnce(
      () =>
        new Promise<WorkspaceRulePlan>((resolve) => {
          resolveSlow = resolve;
        }),
    );
    renderModal();

    fill("Group name pattern", "^team-(?P<ws>.+)$");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    fill("Group name pattern", "^team-(?P<ws>acme)$");
    resolveSlow(PLAN);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Preview" })).toBeEnabled(),
    );
    expect(screen.queryByRole("table", { name: "Rule preview" })).toBeNull();
  });

  it("shows the rule being edited, not the previous one", () => {
    const { rerender } = render(
      <WorkspaceRuleModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        rule={RULE}
        allowedPermissions={["READ", "USE", "EDIT"]}
        maxPermission="EDIT"
      />,
    );
    expect(screen.getByLabelText("Name*")).toHaveValue("tenants");

    rerender(
      <WorkspaceRuleModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        rule={{ ...RULE, id: 8, name: "partners", pattern: "^p-(?P<ws>.+)$" }}
        allowedPermissions={["READ", "USE", "EDIT"]}
        maxPermission="EDIT"
      />,
    );
    expect(screen.getByLabelText("Name*")).toHaveValue("partners");
    expect(screen.getByLabelText("Group name pattern*")).toHaveValue(
      "^p-(?P<ws>.+)$",
    );
  });

  it("does not offer a preview the server would refuse for a permission above the ceiling", () => {
    renderModal({
      rule: { ...RULE, permission: "EDIT" },
      allowedPermissions: ["READ"],
      maxPermission: "READ",
    });

    expect(screen.getByRole("button", { name: "Preview" })).toBeDisabled();
    expect(
      screen.getByText("Choose a permission within the ceiling to preview."),
    ).toBeInTheDocument();
  });

  it("says so when the rule was saved but its grants were not updated", async () => {
    mockUpdate.mockResolvedValue({
      rule: RULE,
      changes: [],
      error: "The rule was saved, but its grants were not updated.",
    });
    renderModal({ rule: RULE });

    fireEvent.change(screen.getByLabelText("Mode"), {
      target: { value: "enforce" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockShowToast).toHaveBeenCalledWith(
        'Rule "tenants" saved. The rule was saved, but its grants were not updated.',
        "error",
      ),
    );
  });
});
