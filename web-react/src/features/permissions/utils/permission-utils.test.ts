import { describe, it, expect } from "vitest";
import { getPermissionUrl } from "./permission-utils";

describe("getPermissionUrl", () => {
  const entityName = "testEntity";
  const identifier = "testId";

  describe("Normal Permissions", () => {
    it("generates user experiment permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "experiments",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/experiments/${identifier}`,
      );
    });

    it("generates group experiment permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "experiments",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/experiments/${identifier}`,
      );
    });

    it("generates user model permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "models",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/registered-models/${identifier}`,
      );
    });

    it("generates group model permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "models",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/registered-models/${identifier}`,
      );
    });

    it("generates user prompt permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "prompts",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/prompts/${identifier}`,
      );
    });

    it("generates group prompt permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "prompts",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/prompts/${identifier}`,
      );
    });

    it("generates user endpoint permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-endpoints",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/endpoints/${identifier}`,
      );
    });

    it("generates group endpoint permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-endpoints",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/endpoints/${identifier}`,
      );
    });

    it("generates user secret permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-secrets",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/secrets/${identifier}`,
      );
    });

    it("generates group secret permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-secrets",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/secrets/${identifier}`,
      );
    });

    it("generates user AI model permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-models",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/model-definitions/${identifier}`,
      );
    });

    it("generates group AI model permission URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-models",
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/model-definitions/${identifier}`,
      );
    });

    it("generates user experiment permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "experiments",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/experiments`,
      );
    });

    it("generates group experiment permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "experiments",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/experiments`,
      );
    });

    it("generates user model permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "models",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/registered-models`,
      );
    });

    it("generates group model permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "models",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/registered-models`,
      );
    });

    it("generates user prompt permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "prompts",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/prompts`,
      );
    });

    it("generates group prompt permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "prompts",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/prompts`,
      );
    });

    it("generates user endpoint permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-endpoints",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/endpoints`,
      );
    });

    it("generates group endpoint permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-endpoints",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/endpoints`,
      );
    });

    it("generates user secret permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-secrets",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/secrets`,
      );
    });

    it("generates group secret permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-secrets",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/secrets`,
      );
    });

    it("generates user AI model permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-models",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/model-definitions`,
      );
    });

    it("generates group AI model permission collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-models",
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/model-definitions`,
      );
    });
  });

  describe("Pattern Permissions (Single)", () => {
    it("generates user experiment pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "experiments",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/experiment-patterns/${identifier}`,
      );
    });

    it("generates group experiment pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "experiments",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/experiment-patterns/${identifier}`,
      );
    });

    it("generates user model pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "models",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/registered-models-patterns/${identifier}`,
      );
    });

    it("generates group model pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "models",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/registered-models-patterns/${identifier}`,
      );
    });

    it("generates user prompt pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "prompts",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/prompts-patterns/${identifier}`,
      );
    });

    it("generates group prompt pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "prompts",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/prompts-patterns/${identifier}`,
      );
    });

    it("generates user endpoint pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-endpoints",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/endpoints-patterns/${identifier}`,
      );
    });

    it("generates group endpoint pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-endpoints",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/endpoints-patterns/${identifier}`,
      );
    });

    it("generates user secret pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-secrets",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/secrets-patterns/${identifier}`,
      );
    });

    it("generates group secret pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-secrets",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/secrets-patterns/${identifier}`,
      );
    });

    it("generates user AI model pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-models",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/model-definitions-patterns/${identifier}`,
      );
    });

    it("generates group AI model pattern URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-models",
        isPattern: true,
        identifier,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/model-definitions-patterns/${identifier}`,
      );
    });
  });

  describe("Pattern Permissions (Collection)", () => {
    it("generates user experiment pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "experiments",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/experiment-patterns`,
      );
    });

    it("generates group experiment pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "experiments",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/experiment-patterns`,
      );
    });

    it("generates user model pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "models",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/registered-models-patterns`,
      );
    });

    it("generates group model pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "models",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/registered-models-patterns`,
      );
    });

    it("generates user prompt pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "prompts",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/prompts-patterns`,
      );
    });

    it("generates group prompt pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "prompts",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/prompts-patterns`,
      );
    });

    it("generates user endpoint pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-endpoints",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/endpoints-patterns`,
      );
    });

    it("generates group endpoint pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-endpoints",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/endpoints-patterns`,
      );
    });

    it("generates user secret pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-secrets",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/secrets-patterns`,
      );
    });

    it("generates group secret pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-secrets",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/secrets-patterns`,
      );
    });

    it("generates user AI model pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "user",
        entityName,
        type: "ai-models",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${entityName}/gateways/model-definitions-patterns`,
      );
    });

    it("generates group AI model pattern collection URL", () => {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type: "ai-models",
        isPattern: true,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/groups/${entityName}/gateways/model-definitions-patterns`,
      );
    });
  });

  describe("URL Encoding", () => {
    it("encodes slashes in entityName and identifier", () => {
      const complexName = "provider/model";
      const complexId = "id/with/slashes";
      const url = getPermissionUrl({
        entityKind: "user",
        entityName: complexName,
        type: "ai-models",
        identifier: complexId,
      });
      expect(url).toBe(
        `/api/2.0/mlflow/permissions/users/${encodeURIComponent(complexName)}/gateways/model-definitions/${encodeURIComponent(complexId)}`,
      );
    });
  });

  describe("Error handling", () => {
    it("throws error for unknown permission type", () => {
      expect(() =>
        getPermissionUrl({
          entityKind: "user",
          entityName,
          // @ts-expect-error - testing invalid type
          type: "unknown",
        }),
      ).toThrow("Unknown permission type");
    });
  });
});
