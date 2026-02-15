import { describe, it, expect } from "vitest";
import { DYNAMIC_API_ENDPOINTS, STATIC_API_ENDPOINTS } from "./api-endpoints";

describe("API Endpoints", () => {
  it("static endpoints are defined", () => {
    expect(STATIC_API_ENDPOINTS.ALL_GROUPS).toBeDefined();
    expect(STATIC_API_ENDPOINTS.GET_CURRENT_USER).toBeDefined();
    expect(STATIC_API_ENDPOINTS.ALL_GATEWAY_ENDPOINTS).toBeDefined();
    expect(STATIC_API_ENDPOINTS.ALL_GATEWAY_SECRETS).toBeDefined();
    expect(STATIC_API_ENDPOINTS.ALL_GATEWAY_MODELS).toBeDefined();
  });

  describe("Dynamic Endpoints", () => {
    // Test a sample of dynamic endpoints to ensure they return strings and boost coverage
    it("returns correct user details URL", () => {
      expect(DYNAMIC_API_ENDPOINTS.GET_USER_DETAILS("testuser")).toBe(
        "/api/2.0/mlflow/users/testuser",
      );
    });

    it("returns correct user experiment permissions URL", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSIONS("testuser"),
      ).toBe("/api/2.0/mlflow/permissions/users/testuser/experiments");
    });

    it("returns correct user experiment permission URL", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION("testuser", "exp1"),
      ).toBe("/api/2.0/mlflow/permissions/users/testuser/experiments/exp1");
    });

    it("returns correct user model permissions URL", () => {
      expect(DYNAMIC_API_ENDPOINTS.USER_MODEL_PERMISSIONS("testuser")).toBe(
        "/api/2.0/mlflow/permissions/users/testuser/registered-models",
      );
    });

    it("returns correct user model permission URL", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_MODEL_PERMISSION("testuser", "model1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/users/testuser/registered-models/model1",
      );
    });

    it("returns correct user prompt permissions URL", () => {
      expect(DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSIONS("testuser")).toBe(
        "/api/2.0/mlflow/permissions/users/testuser/prompts",
      );
    });

    it("returns correct user prompt permission URL", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION("testuser", "prompt1"),
      ).toBe("/api/2.0/mlflow/permissions/users/testuser/prompts/prompt1");
    });

    it("returns correct pattern permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PATTERN_PERMISSIONS("u1"),
      ).toContain("experiment-patterns");
      expect(
        DYNAMIC_API_ENDPOINTS.USER_MODEL_PATTERN_PERMISSIONS("u1"),
      ).toContain("registered-models-patterns");
      expect(
        DYNAMIC_API_ENDPOINTS.USER_PROMPT_PATTERN_PERMISSIONS("u1"),
      ).toContain("prompts-patterns");
    });

    it("returns correct resource user permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.EXPERIMENT_USER_PERMISSIONS("exp1"),
      ).toContain("/experiments/exp1/users");
      expect(DYNAMIC_API_ENDPOINTS.MODEL_USER_PERMISSIONS("mod1")).toContain(
        "/registered-models/mod1/users",
      );
      expect(DYNAMIC_API_ENDPOINTS.PROMPT_USER_PERMISSIONS("p1")).toContain(
        "/prompts/p1/users",
      );
    });

    it("handles encoding for resource IDs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.EXPERIMENT_USER_PERMISSIONS("a/b"),
      ).toContain("a%2Fb");
    });

    it("returns correct group permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PERMISSIONS("g1"),
      ).toContain("/groups/g1/experiments");
      expect(DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PERMISSIONS("g1")).toContain(
        "/groups/g1/registered-models",
      );
      expect(DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PERMISSIONS("g1")).toContain(
        "/groups/g1/prompts",
      );
    });

    it("returns correct group pattern permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PATTERN_PERMISSIONS("g1"),
      ).toContain("experiment-patterns");
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PATTERN_PERMISSION("g1", "pat1"),
      ).toContain("registered-models-patterns/pat1");
    });

    it("returns correct restore URLs", () => {
      expect(DYNAMIC_API_ENDPOINTS.RESTORE_EXPERIMENT("exp1")).toBe(
        "/oidc/trash/experiments/exp1/restore",
      );
      expect(DYNAMIC_API_ENDPOINTS.RESTORE_RUN("run1")).toBe(
        "/oidc/trash/runs/run1/restore",
      );
    });

    it("returns correct gateway user permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GATEWAY_ENDPOINT_USER_PERMISSIONS("endpoint1"),
      ).toBe("/api/2.0/mlflow/permissions/gateways/endpoints/endpoint1/users");
      expect(
        DYNAMIC_API_ENDPOINTS.GATEWAY_SECRET_USER_PERMISSIONS("secret1"),
      ).toBe("/api/2.0/mlflow/permissions/gateways/secrets/secret1/users");
      expect(
        DYNAMIC_API_ENDPOINTS.GATEWAY_MODEL_USER_PERMISSIONS("model1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/gateways/model-definitions/model1/users",
      );
    });

    it("returns correct gateway group permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GATEWAY_ENDPOINT_GROUP_PERMISSIONS("endpoint1"),
      ).toBe("/api/2.0/mlflow/permissions/gateways/endpoints/endpoint1/groups");
      expect(
        DYNAMIC_API_ENDPOINTS.GATEWAY_SECRET_GROUP_PERMISSIONS("secret1"),
      ).toBe("/api/2.0/mlflow/permissions/gateways/secrets/secret1/groups");
      expect(
        DYNAMIC_API_ENDPOINTS.GATEWAY_MODEL_GROUP_PERMISSIONS("model1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/gateways/model-definitions/model1/groups",
      );
    });

    it("returns correct group gateway permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PERMISSIONS("g1"),
      ).toBe("/api/2.0/mlflow/permissions/groups/g1/gateways/endpoints");
      expect(DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PERMISSIONS("g1")).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/gateways/secrets",
      );
      expect(DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PERMISSIONS("g1")).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/gateways/model-definitions",
      );
    });

    it("returns correct group gateway pattern permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS("g1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/gateways/endpoints-patterns",
      );
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PATTERN_PERMISSIONS("g1"),
      ).toBe("/api/2.0/mlflow/permissions/groups/g1/gateways/secrets-patterns");
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PATTERN_PERMISSIONS("g1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/gateways/model-definitions-patterns",
      );
    });

    it("returns correct user gateway permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PERMISSIONS("u1"),
      ).toBe("/api/2.0/mlflow/permissions/users/u1/gateways/endpoints");
      expect(DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PERMISSIONS("u1")).toBe(
        "/api/2.0/mlflow/permissions/users/u1/gateways/secrets",
      );
      expect(DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PERMISSIONS("u1")).toBe(
        "/api/2.0/mlflow/permissions/users/u1/gateways/model-definitions",
      );
    });

    it("returns correct user gateway pattern permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS("u1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/users/u1/gateways/endpoints-patterns",
      );
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PATTERN_PERMISSIONS("u1"),
      ).toBe("/api/2.0/mlflow/permissions/users/u1/gateways/secrets-patterns");
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PATTERN_PERMISSIONS("u1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/users/u1/gateways/model-definitions-patterns",
      );
    });

    it("returns correct user pattern permission URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PATTERN_PERMISSION("u1", "pat1"),
      ).toBe("/api/2.0/mlflow/permissions/users/u1/experiment-patterns/pat1");
      expect(
        DYNAMIC_API_ENDPOINTS.USER_MODEL_PATTERN_PERMISSION("u1", "pat1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/users/u1/registered-models-patterns/pat1",
      );
      expect(
        DYNAMIC_API_ENDPOINTS.USER_PROMPT_PATTERN_PERMISSION("u1", "pat1"),
      ).toBe("/api/2.0/mlflow/permissions/users/u1/prompts-patterns/pat1");
    });

    it("returns correct group permission URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PERMISSION("g1", "exp1"),
      ).toBe("/api/2.0/mlflow/permissions/groups/g1/experiments/exp1");
      expect(DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PERMISSION("g1", "mod1")).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/registered-models/mod1",
      );
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PERMISSION("g1", "prompt1"),
      ).toBe("/api/2.0/mlflow/permissions/groups/g1/prompts/prompt1");
    });

    it("returns correct group pattern permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PATTERN_PERMISSION("g1", "pat1"),
      ).toBe("/api/2.0/mlflow/permissions/groups/g1/experiment-patterns/pat1");
      expect(DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PATTERN_PERMISSIONS("g1")).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/registered-models-patterns",
      );
      expect(DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PATTERN_PERMISSIONS("g1")).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/prompts-patterns",
      );
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PATTERN_PERMISSION("g1", "pat1"),
      ).toBe("/api/2.0/mlflow/permissions/groups/g1/prompts-patterns/pat1");
    });

    it("returns correct resource group permissions URLs", () => {
      expect(DYNAMIC_API_ENDPOINTS.EXPERIMENT_GROUP_PERMISSIONS("exp1")).toBe(
        "/api/2.0/mlflow/permissions/experiments/exp1/groups",
      );
      expect(DYNAMIC_API_ENDPOINTS.MODEL_GROUP_PERMISSIONS("mod1")).toBe(
        "/api/2.0/mlflow/permissions/registered-models/mod1/groups",
      );
      expect(DYNAMIC_API_ENDPOINTS.PROMPT_GROUP_PERMISSIONS("p1")).toBe(
        "/api/2.0/mlflow/permissions/prompts/p1/groups",
      );
    });

    it("returns correct gateway group permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PERMISSION("g1", "end1"),
      ).toBe("/api/2.0/mlflow/permissions/groups/g1/gateways/endpoints/end1");
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PERMISSION("g1", "sec1"),
      ).toBe("/api/2.0/mlflow/permissions/groups/g1/gateways/secrets/sec1");
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PERMISSION("g1", "mod1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/gateways/model-definitions/mod1",
      );
    });

    it("returns correct gateway group pattern permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSION(
          "g1",
          "pat1",
        ),
      ).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/gateways/endpoints-patterns/pat1",
      );
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PATTERN_PERMISSION(
          "g1",
          "pat1",
        ),
      ).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/gateways/secrets-patterns/pat1",
      );
      expect(
        DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PATTERN_PERMISSION(
          "g1",
          "pat1",
        ),
      ).toBe(
        "/api/2.0/mlflow/permissions/groups/g1/gateways/model-definitions-patterns/pat1",
      );
    });

    it("returns correct gateway user permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PERMISSION("u1", "end1"),
      ).toBe("/api/2.0/mlflow/permissions/users/u1/gateways/endpoints/end1");
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PERMISSION("u1", "sec1"),
      ).toBe("/api/2.0/mlflow/permissions/users/u1/gateways/secrets/sec1");
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PERMISSION("u1", "mod1"),
      ).toBe(
        "/api/2.0/mlflow/permissions/users/u1/gateways/model-definitions/mod1",
      );
    });

    it("returns correct gateway user pattern permissions URLs", () => {
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PATTERN_PERMISSION(
          "u1",
          "pat1",
        ),
      ).toBe(
        "/api/2.0/mlflow/permissions/users/u1/gateways/endpoints-patterns/pat1",
      );
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PATTERN_PERMISSION(
          "u1",
          "pat1",
        ),
      ).toBe(
        "/api/2.0/mlflow/permissions/users/u1/gateways/secrets-patterns/pat1",
      );
      expect(
        DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PATTERN_PERMISSION(
          "u1",
          "pat1",
        ),
      ).toBe(
        "/api/2.0/mlflow/permissions/users/u1/gateways/model-definitions-patterns/pat1",
      );
    });

    it("returns correct webhook URLs", () => {
      expect(DYNAMIC_API_ENDPOINTS.WEBHOOK_DETAILS("wh1")).toBe(
        "/oidc/webhook/wh1",
      );
      expect(DYNAMIC_API_ENDPOINTS.TEST_WEBHOOK("wh1")).toBe(
        "/oidc/webhook/wh1/test",
      );
    });
  });
});
