import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { Toast } from "./toast";
import type { ToastType } from "./toast-types";

describe("Toast", () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    const mockOnClose = vi.fn();

    it.each([
        ["success", "bg-green-100"],
        ["error", "bg-red-100"],
        ["info", "bg-blue-100"],
        ["warning", "bg-yellow-100"],
    ])("renders %s toast with correct styles", (type, expectedClass) => {
        render(
            <Toast
                id="1"
                message="Test message"
                type={type as ToastType}
                duration={3000}
                onClose={mockOnClose}
            />
        );

        const toast = screen.getByRole("alert");
        expect(toast.className).toContain(expectedClass);
        expect(screen.getByText("Test message")).toBeDefined();
    });

    it("calls onClose after duration", () => {
        render(
            <Toast
                id="1"
                message="Test message"
                type="info"
                duration={1000}
                onClose={mockOnClose}
            />
        );

        act(() => {
            vi.advanceTimersByTime(1100);
        });

        expect(mockOnClose).toHaveBeenCalled();
    });

    it("calls onClose when close button is clicked", () => {
        render(
            <Toast
                id="1"
                message="Test message"
                type="info"
                duration={3000}
                onClose={mockOnClose}
            />
        );

        const closeButton = screen.getByLabelText("Close");
        fireEvent.click(closeButton);

        expect(mockOnClose).toHaveBeenCalled();
    });

    it("does not call onClose if duration is not provided", () => {
        const localOnClose = vi.fn();
        render(
            <Toast
                id="1"
                message="Test message"
                type="info"
                onClose={localOnClose}
            />
        );

        act(() => {
            vi.advanceTimersByTime(10000);
        });

        expect(localOnClose).not.toHaveBeenCalled();
    });
});
