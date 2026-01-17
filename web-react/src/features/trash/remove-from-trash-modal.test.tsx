import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { RemoveFromTrashModal } from "./remove-from-trash-modal";

describe("RemoveFromTrashModal", () => {
  it("renders correctly with items", () => {
    const items = [{ id: "1", name: "Exp 1" }];
    render(
        <RemoveFromTrashModal 
            isOpen={true} 
            onClose={vi.fn()} 
            onConfirm={vi.fn()} 
            items={items} 
            itemType="experiments" 
            isProcessing={false} 
        />
    );
    expect(screen.getByText("The following experiment(s) will be permanently deleted:")).toBeInTheDocument();
    expect(screen.getByText("Exp 1")).toBeInTheDocument();
  });

  it("calls onConfirm when delete is clicked", () => {
    const onConfirm = vi.fn();
    render(
        <RemoveFromTrashModal 
            isOpen={true} 
            onClose={vi.fn()} 
            onConfirm={onConfirm} 
            items={[]} 
            itemType="experiments" 
            isProcessing={false} 
        />
    );
    
    fireEvent.click(screen.getByText("Delete Permanently"));
    expect(onConfirm).toHaveBeenCalled();
  });
});
