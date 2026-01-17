import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchRuntimeConfig, fetchAuthStatus } from "./auth-service";
import * as runtimeConfigModule from "../../../shared/services/runtime-config";

vi.mock("../../../shared/services/runtime-config");

describe("auth-service", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe("fetchRuntimeConfig", () => {
        it("calls getRuntimeConfig", async () => {
            const mockConfig = { authenticated: true, base_path: "/" };
            vi.spyOn(runtimeConfigModule, "getRuntimeConfig").mockResolvedValue(mockConfig as any);
            
            const result = await fetchRuntimeConfig();
            expect(result).toEqual(mockConfig);
            expect(runtimeConfigModule.getRuntimeConfig).toHaveBeenCalled();
        });
    });

    describe("fetchAuthStatus", () => {
        it("returns authenticated true when config.authenticated is true", async () => {
            vi.spyOn(runtimeConfigModule, "getRuntimeConfig").mockResolvedValue({ authenticated: true } as any);
            
            const result = await fetchAuthStatus();
            expect(result).toEqual({ authenticated: true });
        });

        it("returns authenticated false when config.authenticated is false", async () => {
            vi.spyOn(runtimeConfigModule, "getRuntimeConfig").mockResolvedValue({ authenticated: false } as any);
            
            const result = await fetchAuthStatus();
            expect(result).toEqual({ authenticated: false });
        });

        it("returns authenticated false when config.authenticated is missing", async () => {
            vi.spyOn(runtimeConfigModule, "getRuntimeConfig").mockResolvedValue({} as any);
            
            const result = await fetchAuthStatus();
            expect(result).toEqual({ authenticated: false });
        });
    });
});
