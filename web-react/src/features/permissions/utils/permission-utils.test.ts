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
  });
});
