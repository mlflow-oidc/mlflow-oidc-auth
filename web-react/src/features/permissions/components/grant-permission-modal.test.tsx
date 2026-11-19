import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { GrantPermissionModal } from "./grant-permission-modal";

describe("GrantPermissionModal", () => {
  it("renders correctly", () => {
    render(
      <GrantPermissionModal
        isOpen={true}
        onClose={() => {}}
        onSave={vi.fn()}
        title="Grant Perms"
        label="User"
        options={["user1", "user2"]}
        type="experiments"
      />,
    );
    expect(screen.getByText("Grant Perms")).toBeInTheDocument();
    expect(screen.getByLabelText(/User/i)).toBeInTheDocument();
  });

  it("calls onSave with selected values", async () => {
    const handleSave = vi.fn();
    render(
      <GrantPermissionModal
        isOpen={true}
        onClose={() => {}}
        onSave={handleSave}
        title="Grant Perms"
        label="User"
        options={["user1"]}
        type="experiments"
      />,
    );

    const userSelect = screen.getByLabelText(/User/i);
    fireEvent.change(userSelect, { target: { value: "user1" } });

    const permSelect = screen.getByLabelText(/Permissions/i);
    fireEvent.change(permSelect, { target: { value: "EDIT" } });

    const saveBtn = screen.getByText("Save");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(handleSave).toHaveBeenCalledWith("user1", "EDIT");
    });
  });

  it("accepts a typed name that is not among the options when allowCustomValue is set", async () => {
    const handleSave = vi.fn();
    render(
      <GrantPermissionModal
        isOpen={true}
        onClose={() => {}}
        onSave={handleSave}
        title="Grant Perms"
        label="User"
        options={[]}
        type="experiments"
        allowCustomValue
      />,
    );

    const userInput = screen.getByRole("combobox", { name: /User/i });
    expect(userInput.tagName).toBe("INPUT");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();

    fireEvent.change(userInput, {
      target: { value: "  colleague@example.com " },
    });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => {
      expect(handleSave).toHaveBeenCalledWith("colleague@example.com", "READ");
    });
  });

  it("offers the options as suggestions when allowCustomValue is set", () => {
    render(
      <GrantPermissionModal
        isOpen={true}
        onClose={() => {}}
        onSave={vi.fn()}
        title="Grant Perms"
        label="User"
        options={["user1", "user2"]}
        type="experiments"
        allowCustomValue
      />,
    );

    const input = screen.getByRole("combobox", { name: /User/i });
    const datalist = document.getElementById(input.getAttribute("list") ?? "");
    const suggestions = Array.from(
      datalist?.querySelectorAll("option") ?? [],
    ).map((o) => o.value);
    expect(suggestions).toEqual(["user1", "user2"]);
  });

  it("does not save a whitespace-only name", () => {
    const handleSave = vi.fn();
    render(
      <GrantPermissionModal
        isOpen={true}
        onClose={() => {}}
        onSave={handleSave}
        title="Grant Perms"
        label="User"
        options={[]}
        type="experiments"
        allowCustomValue
      />,
    );

    fireEvent.change(screen.getByRole("combobox", { name: /User/i }), {
      target: { value: "   " },
    });
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    fireEvent.click(screen.getByText("Save"));
    expect(handleSave).not.toHaveBeenCalled();
  });
});
