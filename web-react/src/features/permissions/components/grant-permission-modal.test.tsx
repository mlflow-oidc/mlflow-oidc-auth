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
        />
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
        />
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
});
