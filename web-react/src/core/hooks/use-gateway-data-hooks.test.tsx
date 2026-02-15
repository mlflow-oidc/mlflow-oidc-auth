import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as useAuthModule from "./use-auth";

// Import hooks
import { useAllGatewayEndpoints } from "./use-all-gateway-endpoints";
import { useAllGatewaySecrets } from "./use-all-gateway-secrets";
import { useAllGatewayModels } from "./use-all-gateway-models";

// Import fetchers to mock
import * as gatewayService from "../services/gateway-service";

// Import types
import type {
  GatewayEndpointListItem,
  GatewaySecretListItem,
  GatewayModelListItem,
} from "../../shared/types/entity";

vi.mock("./use-auth");
vi.mock("../services/gateway-service");

describe("Gateway Data Hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
  });

  describe("useAllGatewayEndpoints", () => {
    it("returns all gateway endpoints", async () => {
      const mockEndpoints: GatewayEndpointListItem[] = [
        {
          name: "endpoint-1",
          type: "llm/v1/chat",
          description: "desc 1",
          route_type: "llm/v1/chat",
          auth_type: "bearer",
        },
        {
          name: "endpoint-2",
          type: "llm/v1/completions",
          description: "desc 2",
          route_type: "llm/v1/completions",
          auth_type: "bearer",
        },
      ];
      vi.spyOn(gatewayService, "fetchAllGatewayEndpoints").mockResolvedValue(
        mockEndpoints,
      );

      const { result } = renderHook(() => useAllGatewayEndpoints());

      await waitFor(() => {
        expect(result.current.allGatewayEndpoints).toEqual(mockEndpoints);
      });
    });

    it("returns loading state initially", () => {
      vi.spyOn(gatewayService, "fetchAllGatewayEndpoints").mockReturnValue(
        new Promise(() => {}),
      );

      const { result } = renderHook(() => useAllGatewayEndpoints());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.allGatewayEndpoints).toBeNull();
    });

    it("returns error on failure", async () => {
      vi.spyOn(gatewayService, "fetchAllGatewayEndpoints").mockRejectedValue(
        new Error("Network error"),
      );

      const { result } = renderHook(() => useAllGatewayEndpoints());

      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.error?.message).toBe("Network error");
      });
    });
  });

  describe("useAllGatewaySecrets", () => {
    it("returns all gateway secrets", async () => {
      const mockSecrets: GatewaySecretListItem[] = [
        { key: "secret-1" },
        { key: "secret-2" },
      ];
      vi.spyOn(gatewayService, "fetchAllGatewaySecrets").mockResolvedValue(
        mockSecrets,
      );

      const { result } = renderHook(() => useAllGatewaySecrets());

      await waitFor(() => {
        expect(result.current.allGatewaySecrets).toEqual(mockSecrets);
      });
    });

    it("returns loading state initially", () => {
      vi.spyOn(gatewayService, "fetchAllGatewaySecrets").mockReturnValue(
        new Promise(() => {}),
      );

      const { result } = renderHook(() => useAllGatewaySecrets());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.allGatewaySecrets).toBeNull();
    });

    it("returns error on failure", async () => {
      vi.spyOn(gatewayService, "fetchAllGatewaySecrets").mockRejectedValue(
        new Error("Network error"),
      );

      const { result } = renderHook(() => useAllGatewaySecrets());

      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.error?.message).toBe("Network error");
      });
    });
  });

  describe("useAllGatewayModels", () => {
    it("returns all gateway models", async () => {
      const mockModels: GatewayModelListItem[] = [
        { name: "model-1", source: "openai" },
        { name: "model-2", source: "anthropic" },
      ];
      vi.spyOn(gatewayService, "fetchAllGatewayModels").mockResolvedValue(
        mockModels,
      );

      const { result } = renderHook(() => useAllGatewayModels());

      await waitFor(() => {
        expect(result.current.allGatewayModels).toEqual(mockModels);
      });
    });

    it("returns loading state initially", () => {
      vi.spyOn(gatewayService, "fetchAllGatewayModels").mockReturnValue(
        new Promise(() => {}),
      );

      const { result } = renderHook(() => useAllGatewayModels());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.allGatewayModels).toBeNull();
    });

    it("returns error on failure", async () => {
      vi.spyOn(gatewayService, "fetchAllGatewayModels").mockRejectedValue(
        new Error("Network error"),
      );

      const { result } = renderHook(() => useAllGatewayModels());

      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
        expect(result.current.error?.message).toBe("Network error");
      });
    });
  });
});
