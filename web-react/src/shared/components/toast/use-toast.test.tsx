import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useToast } from "./use-toast";
import { ToastContext } from "./toast-context-val";

describe("useToast", () => {
    it("throws error when used outside ToastProvider", () => {
        expect(() => renderHook(() => useToast())).toThrow("useToast must be used within a ToastProvider");
    });

    it("returns context value when used inside ToastProvider", () => {
        const mockValue = {
            showToast: vi.fn(),
            removeToast: vi.fn(),
        };

        const wrapper = ({ children }: { children: React.ReactNode }) => (
            <ToastContext value={mockValue}>{children}</ToastContext>
        );

        const { result } = renderHook(() => useToast(), { wrapper });
        expect(result.current.showToast).toBeDefined();
    });
});
