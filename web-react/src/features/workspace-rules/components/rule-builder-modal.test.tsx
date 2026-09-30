import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { RuleBuilderModal } from "./rule-builder-modal";

vi.mock("../../../core/hooks/use-all-groups", () => ({
  useAllGroups: () => ({
    allGroups: [
      "team-acme-ds",
      "team-beta-ds",
      "data-scientists",
      "partner:team-acme-ds",
    ],
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  }),
}));

vi.mock("../../../core/hooks/use-api", () => ({
  useApi: () => ({
    data: {
      workspaces: [{ name: "acme" }, { name: "beta" }, { name: "default" }],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

function choose(label: string, typed: string, option: string) {
  const box = screen.getByRole("combobox", { name: label });
  fireEvent.focus(box);
  fireEvent.change(box, { target: { value: typed } });
  const list = screen.getByRole("listbox", { name: label });
  fireEvent.mouseDown(within(list).getByText(option));
}

describe("RuleBuilderModal", () => {
  const onApply = vi.fn();
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    render(
      <RuleBuilderModal isOpen={true} onClose={onClose} onApply={onApply} />,
    );
  });

  it("filters the groups as you type", () => {
    const box = screen.getByRole("combobox", { name: "Group" });
    fireEvent.focus(box);
    fireEvent.change(box, { target: { value: "beta" } });

    const list = screen.getByRole("listbox", { name: "Group" });
    expect(
      within(list)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["team-beta-ds"]);
  });

  it("builds a pattern for the chosen group and workspace", () => {
    choose("Group", "acme", "team-acme-ds");
    choose("Workspace", "ac", "acme");

    expect(screen.getByTestId("rule-builder-pattern")).toHaveTextContent(
      "^team-(?P<ws>acme)-ds$",
    );
    fireEvent.click(screen.getByRole("button", { name: "Use pattern" }));
    expect(onApply).toHaveBeenCalledWith(
      "^team-(?P<ws>acme)-ds$",
      "team-acme-ds → acme",
    );
  });

  it("can cover every group of the same shape", () => {
    choose("Group", "acme", "team-acme-ds");
    choose("Workspace", "ac", "acme");
    fireEvent.click(
      screen.getByLabelText(/Match every group with the same shape/),
    );

    fireEvent.click(screen.getByRole("button", { name: "Use pattern" }));
    expect(onApply).toHaveBeenCalledWith(
      "^team-(?P<ws>[a-z0-9-]+)-ds$",
      "team-*-ds",
    );
  });

  it("explains, and offers nothing, when the group name lacks the workspace", () => {
    choose("Group", "data", "data-scientists");
    choose("Workspace", "ac", "acme");

    expect(screen.getByRole("alert")).toHaveTextContent(
      "does not contain the workspace name",
    );
    expect(screen.getByRole("button", { name: "Use pattern" })).toBeDisabled();
  });

  it("does not offer the default workspace", () => {
    const box = screen.getByRole("combobox", { name: "Workspace" });
    fireEvent.focus(box);

    const list = screen.getByRole("listbox", { name: "Workspace" });
    expect(
      within(list)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["acme", "beta"]);
  });

  it("picks with the keyboard, and Escape closes only the list", () => {
    const box = screen.getByRole("combobox", { name: "Group" });
    fireEvent.focus(box);
    fireEvent.change(box, { target: { value: "team" } });
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(box).toHaveValue("team-acme-ds");

    fireEvent.focus(box);
    fireEvent.keyDown(box, { key: "Escape" });
    expect(screen.queryByRole("listbox", { name: "Group" })).toBeNull();
    expect(onClose).not.toHaveBeenCalled();
  });
});
