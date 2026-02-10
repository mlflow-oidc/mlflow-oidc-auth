import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePermissionsManagement } from "./use-permissions-management";
import * as httpModule from "../../../core/services/http";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import type { PermissionType } from "../../../shared/types/entity";
import type { ToastContextType } from "../../../shared/components/toast/toast-context-val";
import { getRuntimeConfig } from "../../../shared/services/runtime-config";

vi.mock("../../../core/services/http");
vi.mock("../../../shared/services/runtime-config", () => ({
  getRuntimeConfig: vi.fn(() =>
    Promise.resolve({
      basePath: "",
      uiPath: "",
      provider: "",
      authenticated: true,
    }),
  ),
}));
vi.mock("../../../shared/components/toast/use-toast");

describe("usePermissionsManagement", () => {
  const mockRefresh = vi.fn();
  const mockShowToast = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as ToastContextType);
  });

  it("initializes with default state", () => {
    const { result } = renderHook(() =>
      usePermissionsManagement({
        resourceId: "res1",
        resourceType: "experiments",
        refresh: mockRefresh,
      }),
    );

    expect(result.current.isModalOpen).toBe(false);
    expect(result.current.editingItem).toBeNull();
    expect(result.current.isSaving).toBe(false);
  });

  it("handles edit click", () => {
    const { result } = renderHook(() =>
      usePermissionsManagement({
        resourceId: "res1",
        resourceType: "experiments",
        refresh: mockRefresh,
      }),
    );

    act(() => {
      result.current.handleEditClick({
        name: "user1",
        permission: "READ",
        kind: "user",
      });
    });

    expect(result.current.isModalOpen).toBe(true);
    expect(result.current.editingItem).toEqual({
      name: "user1",
      permission: "READ",
      kind: "user",
    });
  });

  it("handles modal close", () => {
    const { result } = renderHook(() =>
      usePermissionsManagement({
        resourceId: "res1",
        resourceType: "experiments",
        refresh: mockRefresh,
      }),
    );

    act(() => {
      result.current.handleEditClick({
        name: "user1",
        permission: "READ",
        kind: "user",
      });
    });
    expect(result.current.isModalOpen).toBe(true);

    act(() => {
      result.current.handleModalClose();
    });

    expect(result.current.isModalOpen).toBe(false);
    expect(result.current.editingItem).toBeNull();
  });

  const combinations: {
    type: PermissionType;
    kind: "user" | "group";
    expectedUrl: string;
  }[] = [
    {
      type: "experiments",
      kind: "user",
      expectedUrl: "/api/2.0/mlflow/permissions/users/name1/experiments/id1",
    },
    {
      type: "experiments",
      kind: "group",
      expectedUrl: "/api/2.0/mlflow/permissions/groups/name1/experiments/id1",
    },
    {
      type: "models",
      kind: "user",
      expectedUrl:
        "/api/2.0/mlflow/permissions/users/name1/registered-models/id1",
    },
    {
      type: "models",
      kind: "group",
      expectedUrl:
        "/api/2.0/mlflow/permissions/groups/name1/registered-models/id1",
    },
    {
      type: "prompts",
      kind: "user",
      expectedUrl: "/api/2.0/mlflow/permissions/users/name1/prompts/id1",
    },
    {
      type: "prompts",
      kind: "group",
      expectedUrl: "/api/2.0/mlflow/permissions/groups/name1/prompts/id1",
    },
    {
      type: "endpoints",
      kind: "user",
      expectedUrl:
        "/api/2.0/mlflow/permissions/users/name1/gateways/endpoints/id1",
    },
    {
      type: "endpoints",
      kind: "group",
      expectedUrl:
        "/api/2.0/mlflow/permissions/groups/name1/gateways/endpoints/id1",
    },
  ];

  describe("CRUD operations across all resource types and kinds", () => {
    combinations.forEach(({ type, kind, expectedUrl }) => {
      describe(`${type} - ${kind}`, () => {
        it(`successfully updates permission for ${type} ${kind}`, async () => {
          vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
          const { result } = renderHook(() =>
            usePermissionsManagement({
              resourceId: "id1",
              resourceType: type,
              refresh: mockRefresh,
            }),
          );

          act(() => {
            result.current.handleEditClick({
              name: "name1",
              permission: "READ",
              kind: kind,
            });
          });

          await act(async () => {
            await result.current.handleSavePermission("MANAGE");
          });

          expect(httpModule.http).toHaveBeenCalledWith(
            expectedUrl,
            expect.objectContaining({ method: "PATCH" }),
          );
        });

        it(`successfully removes permission for ${type} ${kind}`, async () => {
          vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
          const { result } = renderHook(() =>
            usePermissionsManagement({
              resourceId: "id1",
              resourceType: type,
              refresh: mockRefresh,
            }),
          );

          await act(async () => {
            await result.current.handleRemovePermission({
              name: "name1",
              kind: kind,
              permission: "READ",
            });
          });

          expect(httpModule.http).toHaveBeenCalledWith(
            expectedUrl,
            expect.objectContaining({ method: "DELETE" }),
          );
        });

        it(`successfully grants permission for ${type} ${kind}`, async () => {
          vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
          const { result } = renderHook(() =>
            usePermissionsManagement({
              resourceId: "id1",
              resourceType: type,
              refresh: mockRefresh,
            }),
          );

          await act(async () => {
            await result.current.handleGrantPermission("name1", "EDIT", kind);
          });

          expect(httpModule.http).toHaveBeenCalledWith(
            expectedUrl,
            expect.objectContaining({ method: "POST" }),
          );
        });
      });
    });
  });

  it("handles failure during grant", async () => {
    vi.spyOn(httpModule, "http").mockRejectedValue(new Error("Fail"));
    const { result } = renderHook(() =>
      usePermissionsManagement({
        resourceId: "id1",
        resourceType: "experiments",
        refresh: mockRefresh,
      }),
    );

    let success;
    await act(async () => {
      success = await result.current.handleGrantPermission(
        "user2",
        "EDIT",
        "user",
      );
    });

    expect(success).toBe(false);
    expect(mockShowToast).toHaveBeenCalledWith(
      expect.stringContaining("Failed"),
      "error",
    );
  });

  it("prefixes URL with basePath from runtime config", async () => {
    vi.mocked(getRuntimeConfig).mockResolvedValue({
      basePath: "/mlflow",
      uiPath: "",
      provider: "",
      authenticated: true,
      gen_ai_gateway_enabled: false,
    });
    vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
    const { result } = renderHook(() =>
      usePermissionsManagement({
        resourceId: "id1",
        resourceType: "experiments",
        refresh: mockRefresh,
      }),
    );

    await act(async () => {
      await result.current.handleGrantPermission("user1", "READ", "user");
    });

    expect(httpModule.http).toHaveBeenCalledWith(
      "/mlflow/api/2.0/mlflow/permissions/users/user1/experiments/id1",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("does not update if editingItem is null", async () => {
    const { result } = renderHook(() =>
      usePermissionsManagement({
        resourceId: "id1",
        resourceType: "experiments",
        refresh: mockRefresh,
      }),
    );

    await act(async () => {
      await result.current.handleSavePermission("MANAGE");
    });

    expect(httpModule.http).not.toHaveBeenCalled();
  });
});
