import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AddRegexRuleModal } from "./add-regex-rule-modal";
import { workspaceScopeWrapper } from "../../../tests/workspace-scope-wrapper";

describe("AddRegexRuleModal", () => {
  it("renders when open", () => {
    render(
      <AddRegexRuleModal
        isOpen={true}
        onClose={() => {}}
        onSave={vi.fn()}
        type="experiments"
      />,
    );
    expect(screen.getByText("Add New Regex Rule")).toBeInTheDocument();
  });

  it("validates regex input", async () => {
    render(
      <AddRegexRuleModal
        isOpen={true}
        onClose={() => {}}
        onSave={vi.fn()}
        type="experiments"
      />,
    );

    const regexInput = screen.getByLabelText(/Regex/i);
    fireEvent.change(regexInput, { target: { value: "[" } }); // Invalid regex

    const saveBtn = screen.getByText("Save");
    fireEvent.click(saveBtn);

    expect(
      await screen.findByText(
        "Invalid regular expression. Please enter a valid Python regex.",
      ),
    ).toBeInTheDocument();
  });

  it("validates empty regex input", async () => {
    render(
      <AddRegexRuleModal
        isOpen={true}
        onClose={() => {}}
        onSave={vi.fn()}
        type="experiments"
      />,
    );

    const saveBtn = screen.getByText("Save");
    fireEvent.click(saveBtn);

    expect(await screen.findByText("Regex is required.")).toBeInTheDocument();
  });

  it("validates priority input", async () => {
    render(
      <AddRegexRuleModal
        isOpen={true}
        onClose={() => {}}
        onSave={vi.fn()}
        type="experiments"
      />,
    );

    // Regex valid
    const regexInput = screen.getByLabelText(/Regex/i);
    fireEvent.change(regexInput, { target: { value: ".*" } });

    const priorityInput = screen.getByLabelText(/Priority/i);
    fireEvent.change(priorityInput, { target: { value: "-1" } }); // Invalid priority

    const saveBtn = screen.getByText("Save");
    fireEvent.click(saveBtn);

    expect(
      await screen.findByText("Priority must be a non-negative integer."),
    ).toBeInTheDocument();
  });

  it("calls onSave when valid", async () => {
    const handleSave = vi.fn();
    render(
      <AddRegexRuleModal
        isOpen={true}
        onClose={() => {}}
        onSave={handleSave}
        type="experiments"
      />,
    );

    const regexInput = screen.getByLabelText(/Regex/i);
    fireEvent.change(regexInput, { target: { value: "^test_.*" } });

    const priorityInput = screen.getByLabelText(/Priority/i);
    fireEvent.change(priorityInput, { target: { value: "10" } });

    const saveBtn = screen.getByText("Save");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(handleSave).toHaveBeenCalledWith("^test_.*", "READ", 10);
    });
  });

  it("with a workspace selected, says the pattern applies only there", () => {
    render(
      <AddRegexRuleModal
        isOpen={true}
        type="models"
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
      { wrapper: workspaceScopeWrapper(true, "team-a") },
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "This pattern will apply only in workspace team-a.",
    );
  });

  it("under All Workspaces, says the pattern applies in every workspace", () => {
    render(
      <AddRegexRuleModal
        isOpen={true}
        type="models"
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
      { wrapper: workspaceScopeWrapper(true, null) },
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "This pattern will apply in every workspace.",
    );
  });

  it("says nothing about workspaces when they are disabled", () => {
    render(
      <AddRegexRuleModal
        isOpen={true}
        type="models"
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
      { wrapper: workspaceScopeWrapper(false, null) },
    );
    expect(screen.queryByText(/every workspace/)).toBeNull();
  });
});
