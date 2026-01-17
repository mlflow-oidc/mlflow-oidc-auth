import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useAuth } from "./use-auth";
import * as runtimeConfig from "../../shared/context/use-runtime-config";

vi.mock("../../shared/context/use-runtime-config");

describe("useAuth", () => {
    it("returns isAuthenticated true when config.authenticated is true", () => {
        vi.spyOn(runtimeConfig, "useRuntimeConfig").mockReturnValue({ authenticated: true } as any);
        const { result } = renderHook(() => useAuth());
        expect(result.current.isAuthenticated).toBe(true);
    });

    it("returns isAuthenticated false when config.authenticated is false", () => {
        vi.spyOn(runtimeConfig, "useRuntimeConfig").mockReturnValue({ authenticated: false } as any);
        const { result } = renderHook(() => useAuth());
        expect(result.current.isAuthenticated).toBe(false);
    });
});
