import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { EditPermissionModal } from "./edit-permission-modal";

describe("EditPermissionModal", () => {
  it("renders correctly for regular permission", () => {
    const item = { name: "test", permission: "READ", kind: "user" };
    render(
      <EditPermissionModal
        isOpen={true}
        onClose={() => {}}
        onSave={vi.fn()}
        item={item as any}
        username="testuser"
        type="experiments"
      />,
    );

    expect(
      screen.getByText(/Edit Experiment.* test permissions/),
    ).toBeInTheDocument();
  });

  it("calls onSave with new permission", async () => {
    const onSave = vi.fn();
    const item = { name: "test", permission: "READ", kind: "user" };
    render(
      <EditPermissionModal
        isOpen={true}
        onClose={() => {}}
        onSave={onSave}
        item={item as any}
        username="testuser"
        type="experiments"
      />,
    );

    const select = screen.getByLabelText("Permission Level");
    fireEvent.change(select, { target: { value: "EDIT" } });

    fireEvent.click(screen.getByText("Ok"));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("EDIT");
    });
  });

  it("handles regex rule display", () => {
    const item = {
      regex: ".*",
      priority: 1,
      permission: "READ",
      kind: "regex",
      id: 1,
    };
    render(
      <EditPermissionModal
        isOpen={true}
        onClose={() => {}}
        onSave={vi.fn()}
        item={item as any}
        username="testuser"
        type="experiments"
      />,
    );
    expect(screen.getByText("Manage Regex Rule .*")).toBeInTheDocument();
    expect(screen.getByDisplayValue(".*")).toBeInTheDocument();
  });
});
