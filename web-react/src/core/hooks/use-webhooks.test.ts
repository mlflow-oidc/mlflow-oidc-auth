import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useWebhooks } from "./use-webhooks";
import * as webhookService from "../services/webhook-service";
import * as useAuthModule from "./use-auth";

vi.mock("../services/webhook-service");
vi.mock("./use-auth");

describe("useWebhooks", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.spyOn(useAuthModule, "useAuth").mockReturnValue({ isAuthenticated: true } as any);
    });

    it("returns webhooks data", async () => {
        const mockWebhooks = {
            webhooks: [
                { id: "1", name: "Webhook 1", url: "http://example.com/1" }
            ]
        };
        vi.spyOn(webhookService, "listWebhooks").mockResolvedValue(mockWebhooks as any);

        const { result } = renderHook(() => useWebhooks());

        await waitFor(() => {
            expect(result.current.webhooks).toEqual(mockWebhooks.webhooks);
            expect(result.current.isLoading).toBe(false);
        });
    });

    it("returns empty array and error on failure", async () => {
        const mockError = new Error("Failed to fetch");
        vi.spyOn(webhookService, "listWebhooks").mockRejectedValue(mockError);

        const { result } = renderHook(() => useWebhooks());

        await waitFor(() => {
            expect(result.current.webhooks).toEqual([]);
            expect(result.current.error).toEqual(mockError);
            expect(result.current.isLoading).toBe(false);
        });
    });
});
