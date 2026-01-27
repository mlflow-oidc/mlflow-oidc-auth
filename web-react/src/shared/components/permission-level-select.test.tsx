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
      />
    );
    expect(screen.getByLabelText("Custom Label*")).toBeInTheDocument();
  });

  it("renders all permission levels options", () => {
    render(<PermissionLevelSelect value="READ" onChange={vi.fn()} />);
    
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(4);
    expect(options[0]).toHaveTextContent("READ");
    expect(options[1]).toHaveTextContent("EDIT");
    expect(options[2]).toHaveTextContent("MANAGE");
    expect(options[3]).toHaveTextContent("NO_PERMISSIONS");
  });

  it("respects disabled prop", () => {
    render(<PermissionLevelSelect value="READ" onChange={vi.fn()} disabled />);
    expect(screen.getByRole("combobox")).toBeDisabled();
  });
});
