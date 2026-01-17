import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AddRegexRuleModal } from "./add-regex-rule-modal";

describe("AddRegexRuleModal", () => {
  it("renders when open", () => {
    render(<AddRegexRuleModal isOpen={true} onClose={() => {}} onSave={vi.fn()} />);
    expect(screen.getByText("Add New Regex Rule")).toBeInTheDocument();
  });

  it("validates regex input", async () => {
    render(<AddRegexRuleModal isOpen={true} onClose={() => {}} onSave={vi.fn()} />);
    
    const regexInput = screen.getByLabelText(/Regex/i);
    fireEvent.change(regexInput, { target: { value: "[" } }); // Invalid regex
    
    const saveBtn = screen.getByText("Save");
    fireEvent.click(saveBtn);
    
    expect(await screen.findByText("Invalid regular expression. Please enter a valid Python regex.")).toBeInTheDocument();
  });

  it("validates priority input", async () => {
    render(<AddRegexRuleModal isOpen={true} onClose={() => {}} onSave={vi.fn()} />);
    
     // Regex valid
    const regexInput = screen.getByLabelText(/Regex/i);
    fireEvent.change(regexInput, { target: { value: ".*" } });

    const priorityInput = screen.getByLabelText(/Priority/i);
    fireEvent.change(priorityInput, { target: { value: "-1" } }); // Invalid priority
    
    const saveBtn = screen.getByText("Save");
    fireEvent.click(saveBtn);
    
    expect(await screen.findByText("Priority must be a non-negative integer.")).toBeInTheDocument();
  });

  it("calls onSave when valid", async () => {
    const handleSave = vi.fn();
    render(<AddRegexRuleModal isOpen={true} onClose={() => {}} onSave={handleSave} />);
    
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
});
