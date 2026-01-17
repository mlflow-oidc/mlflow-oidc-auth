import { describe, it, expect, vi } from "vitest";
import { resolveUrl } from "./api-utils";
import * as runtimeConfig from "../../shared/services/runtime-config";

describe("api-utils", () => {
    it("resolveUrl builds correct URL with params", async () => {
        const mockConfig = { basePath: "/api/v1" };
        vi.spyOn(runtimeConfig, "getRuntimeConfig").mockResolvedValue(mockConfig as any);

        const url = await resolveUrl("/users", { limit: 10, offset: 0 });
        expect(url).toBe("/api/v1/users?limit=10&offset=0");
    });

    it("resolveUrl handles unknown params", async () => {
        const mockConfig = { basePath: "/api/v1" };
        vi.spyOn(runtimeConfig, "getRuntimeConfig").mockResolvedValue(mockConfig as any);

        const url = await resolveUrl("/users", { valid: true, invalid: undefined, nullVal: null });
        expect(url).toBe("/api/v1/users?valid=true");
    });
});
