import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PermissionLevelSelect } from "./permission-level-select";

describe("PermissionLevelSelect", () => {
  it("renders correctly with default props", () => {
    render(<PermissionLevelSelect value="READ" onChange={vi.fn()} />);

    expect(screen.getByLabelText(/Permissions/i)).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveValue("READ");
  });

  it("calls onChange when selection changes", () => {
    const handleChange = vi.fn();
    render(<PermissionLevelSelect value="READ" onChange={handleChange} />);

    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "EDIT" } });

    expect(handleChange).toHaveBeenCalledWith("EDIT");
  });

  it("renders with custom label", () => {
    render(
      <PermissionLevelSelect
        value="READ"
        onChange={vi.fn()}
        label="Custom Label"
      />,
    );
    expect(screen.getByLabelText("Custom Label*")).toBeInTheDocument();
  });

  it("renders default permission levels options when no type is provided", () => {
    render(<PermissionLevelSelect value="READ" onChange={vi.fn()} />);

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(4);
    expect(options.map((o) => o.textContent)).toEqual([
      "READ",
      "EDIT",
      "MANAGE",
      "NO_PERMISSIONS",
    ]);
  });

  it("renders gateway permission levels options (including USE) when type is ai-endpoints", () => {
    render(
      <PermissionLevelSelect
        value="READ"
        onChange={vi.fn()}
        type="ai-endpoints"
      />,
    );

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(5);
    expect(options.map((o) => o.textContent)).toEqual([
      "READ",
      "USE",
      "EDIT",
      "MANAGE",
      "NO_PERMISSIONS",
    ]);
  });

  it("renders gateway permission levels options (including USE) when type is ai-secrets", () => {
    render(
      <PermissionLevelSelect
        value="READ"
        onChange={vi.fn()}
        type="ai-secrets"
      />,
    );

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(5);
    expect(options.map((o) => o.textContent)).toEqual([
      "READ",
      "USE",
      "EDIT",
      "MANAGE",
      "NO_PERMISSIONS",
    ]);
  });

  it("renders gateway permission levels options (including USE) when type is ai-models", () => {
    render(
      <PermissionLevelSelect
        value="READ"
        onChange={vi.fn()}
        type="ai-models"
      />,
    );

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(5);
    expect(options.map((o) => o.textContent)).toEqual([
      "READ",
      "USE",
      "EDIT",
      "MANAGE",
      "NO_PERMISSIONS",
    ]);
  });

  it("renders default permission levels options when type is experiments", () => {
    render(
      <PermissionLevelSelect
        value="READ"
        onChange={vi.fn()}
        type="experiments"
      />,
    );

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(4);
    expect(options.map((o) => o.textContent)).toEqual([
      "READ",
      "EDIT",
      "MANAGE",
      "NO_PERMISSIONS",
    ]);
  });

  it("respects disabled prop", () => {
    render(<PermissionLevelSelect value="READ" onChange={vi.fn()} disabled />);
    expect(screen.getByRole("combobox")).toBeDisabled();
  });
});
