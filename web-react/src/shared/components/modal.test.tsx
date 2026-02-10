import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Modal } from "./modal";

describe("Modal", () => {
  it("renders when open", () => {
    render(
      <Modal isOpen={true} onClose={() => {}} title="Test Modal">
        <div>Modal Content</div>
      </Modal>,
    );
    expect(screen.getByText("Test Modal")).toBeInTheDocument();
    expect(screen.getByText("Modal Content")).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    render(
      <Modal isOpen={false} onClose={() => {}} title="Test Modal">
        <div>Modal Content</div>
      </Modal>,
    );
    const dialog = screen.queryByRole("dialog", { hidden: true });
    expect(dialog).toBeInTheDocument();
    expect(dialog).not.toHaveAttribute("open");
  });

  it("calls onClose when pressing Escape", () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose} title="Test Modal">
        <div>Content</div>
      </Modal>,
    );

    const dialog = screen.getByRole("dialog");
    fireEvent(dialog, new Event("cancel"));
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking backdrop", () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose} title="Test Modal">
        <div>Content</div>
      </Modal>,
    );

    fireEvent.click(screen.getByRole("dialog"));
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking close button", () => {
    const handleClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={handleClose} title="Test Modal">
        <div>Content</div>
      </Modal>,
    );

    const closeBtn = screen.getByRole("button", { name: "Close modal" });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("locks body scroll when open", () => {
    const { unmount } = render(
      <Modal isOpen={true} onClose={() => {}} title="Test Modal">
        <div>Content</div>
      </Modal>,
    );
    expect(document.body.style.overflow).toBe("hidden");

    unmount();
    expect(document.body.style.overflow).toBe("unset");
  });
});
