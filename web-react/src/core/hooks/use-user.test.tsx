import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useUser, UserContext } from "./use-user";

describe("useUser", () => {
    it("throws error when used outside UserProvider", () => {
        expect(() => renderHook(() => useUser())).toThrow("useUser must be used inside <UserProvider>");
    });

    it("returns context value when used inside UserProvider", () => {
        const mockValue = {
            currentUser: { username: "test", is_admin: false },
            isLoading: false,
            error: null,
            refresh: vi.fn(),
        };

        const wrapper = ({ children }: { children: React.ReactNode }) => (
            <UserContext value={mockValue as any}>{children}</UserContext>
        );

        const { result } = renderHook(() => useUser(), { wrapper });
        expect(result.current.currentUser?.username).toBe("test");
    });
});
