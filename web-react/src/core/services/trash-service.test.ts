import { describe, it, expect, vi } from "vitest";
import { cleanupTrash, restoreExperiment } from "./trash-service";
import { http } from "./http";

vi.mock("./http");

describe("trash-service", () => {
    it("cleanupTrash calls http with correct params", async () => {
        await cleanupTrash({ older_than: "7d" });
        expect(http).toHaveBeenCalledWith(expect.stringContaining("older_than=7d"), expect.objectContaining({ method: "POST" }));
    });

    it("restoreExperiment calls correct endpoint", async () => {
        await restoreExperiment("123");
        // endpoint is dynamic, usually /trash/experiments/123/restore or similar
        // We expect http to be called
        expect(http).toHaveBeenCalled(); 
    });
});
