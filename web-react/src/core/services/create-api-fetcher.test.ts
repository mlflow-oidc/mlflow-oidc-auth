import { describe, it, expect } from "vitest";
import { createStaticApiFetcher, createDynamicApiFetcher } from "./create-api-fetcher";

describe("create-api-fetcher", () => {
    it("createStaticApiFetcher returns a function", () => {
        const fetcher = createStaticApiFetcher({
            endpointKey: "ALL_GROUPS",
            responseType: [],
        });
        expect(typeof fetcher).toBe("function");
    });

    it("createDynamicApiFetcher returns a function", () => {
        const fetcher = createDynamicApiFetcher({
            endpointKey: "EXPERIMENT_USER_PERMISSIONS",
            responseType: [],
        });
        expect(typeof fetcher).toBe("function");
    });
});
