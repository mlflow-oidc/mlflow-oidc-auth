import { describe, it, expect } from "vitest";
import * as gatewayService from "./gateway-service";

describe("gateway-service", () => {
  describe("static list fetchers", () => {
    it("fetchAllGatewayEndpoints is defined", () => {
      expect(gatewayService.fetchAllGatewayEndpoints).toBeDefined();
      expect(typeof gatewayService.fetchAllGatewayEndpoints).toBe("function");
    });

    it("fetchAllGatewaySecrets is defined", () => {
      expect(gatewayService.fetchAllGatewaySecrets).toBeDefined();
      expect(typeof gatewayService.fetchAllGatewaySecrets).toBe("function");
    });

    it("fetchAllGatewayModels is defined", () => {
      expect(gatewayService.fetchAllGatewayModels).toBeDefined();
      expect(typeof gatewayService.fetchAllGatewayModels).toBe("function");
    });
  });

  describe("user permission fetchers", () => {
    it("fetchUserGatewayEndpointPermissions is defined", () => {
      expect(gatewayService.fetchUserGatewayEndpointPermissions).toBeDefined();
    });

    it("fetchUserGatewaySecretPermissions is defined", () => {
      expect(gatewayService.fetchUserGatewaySecretPermissions).toBeDefined();
    });

    it("fetchUserGatewayModelPermissions is defined", () => {
      expect(gatewayService.fetchUserGatewayModelPermissions).toBeDefined();
    });
  });

  describe("user pattern permission fetchers", () => {
    it("fetchUserGatewayEndpointPatternPermissions is defined", () => {
      expect(
        gatewayService.fetchUserGatewayEndpointPatternPermissions,
      ).toBeDefined();
    });

    it("fetchUserGatewaySecretPatternPermissions is defined", () => {
      expect(
        gatewayService.fetchUserGatewaySecretPatternPermissions,
      ).toBeDefined();
    });

    it("fetchUserGatewayModelPatternPermissions is defined", () => {
      expect(
        gatewayService.fetchUserGatewayModelPatternPermissions,
      ).toBeDefined();
    });
  });

  describe("group permission fetchers", () => {
    it("fetchGroupGatewayEndpointPermissions is defined", () => {
      expect(gatewayService.fetchGroupGatewayEndpointPermissions).toBeDefined();
    });

    it("fetchGroupGatewaySecretPermissions is defined", () => {
      expect(gatewayService.fetchGroupGatewaySecretPermissions).toBeDefined();
    });

    it("fetchGroupGatewayModelPermissions is defined", () => {
      expect(gatewayService.fetchGroupGatewayModelPermissions).toBeDefined();
    });
  });

  describe("group pattern permission fetchers", () => {
    it("fetchGroupGatewayEndpointPatternPermissions is defined", () => {
      expect(
        gatewayService.fetchGroupGatewayEndpointPatternPermissions,
      ).toBeDefined();
    });

    it("fetchGroupGatewaySecretPatternPermissions is defined", () => {
      expect(
        gatewayService.fetchGroupGatewaySecretPatternPermissions,
      ).toBeDefined();
    });

    it("fetchGroupGatewayModelPatternPermissions is defined", () => {
      expect(
        gatewayService.fetchGroupGatewayModelPatternPermissions,
      ).toBeDefined();
    });
  });

  describe("resource user permission fetchers", () => {
    it("fetchGatewayEndpointUserPermissions is defined", () => {
      expect(gatewayService.fetchGatewayEndpointUserPermissions).toBeDefined();
    });

    it("fetchGatewaySecretUserPermissions is defined", () => {
      expect(gatewayService.fetchGatewaySecretUserPermissions).toBeDefined();
    });

    it("fetchGatewayModelUserPermissions is defined", () => {
      expect(gatewayService.fetchGatewayModelUserPermissions).toBeDefined();
    });
  });

  describe("resource group permission fetchers", () => {
    it("fetchGatewayEndpointGroupPermissions is defined", () => {
      expect(gatewayService.fetchGatewayEndpointGroupPermissions).toBeDefined();
    });

    it("fetchGatewaySecretGroupPermissions is defined", () => {
      expect(gatewayService.fetchGatewaySecretGroupPermissions).toBeDefined();
    });

    it("fetchGatewayModelGroupPermissions is defined", () => {
      expect(gatewayService.fetchGatewayModelGroupPermissions).toBeDefined();
    });
  });
});
