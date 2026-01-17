import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
    applyTheme,
    getInitialIsDarkState,
    initializeTheme,
    useTheme,
    DARK_MODE_TOGGLE_ENABLED_KEY,
    THEME_PREF_KEY
} from "./theme-utils";

// Mock localStorage
const localStorageMock = (() => {
    let store: Record<string, string> = {};
    return {
        getItem: (key: string) => store[key] || null,
        setItem: (key: string, value: string) => { store[key] = value; },
        clear: () => { store = {}; },
    };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });
Object.defineProperty(window, "matchMedia", {
    value: vi.fn().mockReturnValue({ matches: false }),
});

describe("theme-utils", () => {
    beforeEach(() => {
        localStorageMock.clear();
        document.documentElement.classList.remove("dark");
    });

    describe("applyTheme", () => {
        it("adds dark class when isDark is true", () => {
            applyTheme(true);
            expect(document.documentElement.classList.contains("dark")).toBe(true);
            expect(localStorage.getItem(DARK_MODE_TOGGLE_ENABLED_KEY)).toBe("true");
            expect(localStorage.getItem(THEME_PREF_KEY)).toBe("dark");
        });

        it("removes dark class when isDark is false", () => {
            document.documentElement.classList.add("dark");
            applyTheme(false);
            expect(document.documentElement.classList.contains("dark")).toBe(false);
            expect(localStorage.getItem(DARK_MODE_TOGGLE_ENABLED_KEY)).toBe("false");
            expect(localStorage.getItem(THEME_PREF_KEY)).toBe("light");
        });
    });

    describe("getInitialIsDarkState", () => {
        it("returns true when localStorage has true", () => {
            localStorage.setItem(DARK_MODE_TOGGLE_ENABLED_KEY, "true");
            expect(getInitialIsDarkState()).toBe(true);
        });

        it("returns false when localStorage has false", () => {
            localStorage.setItem(DARK_MODE_TOGGLE_ENABLED_KEY, "false");
            expect(getInitialIsDarkState()).toBe(false);
        });

        it("falls back to system preference when no localStorage value", () => {
            expect(getInitialIsDarkState()).toBe(false); // matchMedia mocked to return false
        });
    });

    describe("initializeTheme", () => {
        it("applies theme based on initial state", () => {
            localStorage.setItem(DARK_MODE_TOGGLE_ENABLED_KEY, "true");
            initializeTheme();
            expect(document.documentElement.classList.contains("dark")).toBe(true);
        });
    });

    describe("useTheme", () => {
        it("provides toggleTheme function", () => {
            const { result } = renderHook(() => useTheme());
            expect(result.current.isDark).toBe(false);

            act(() => {
                result.current.toggleTheme();
            });

            expect(result.current.isDark).toBe(true);
        });
    });
});
