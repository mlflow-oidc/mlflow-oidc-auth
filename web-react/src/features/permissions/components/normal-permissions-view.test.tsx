import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NormalPermissionsView } from "./normal-permissions-view";
import * as httpModule from "../../../core/services/http";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import * as useSearchModule from "../../../core/hooks/use-search";
import * as useExpHooks from "../../../core/hooks/use-user-experiment-permissions";
import * as useModelHooks from "../../../core/hooks/use-user-model-permissions";
import * as usePromptHooks from "../../../core/hooks/use-user-prompt-permissions";
import * as useGroupExpHooks from "../../../core/hooks/use-group-experiment-permissions";
import * as useGroupModelHooks from "../../../core/hooks/use-group-model-permissions";
import * as useGroupPromptHooks from "../../../core/hooks/use-group-prompt-permissions";
import * as useAllExpHooks from "../../../core/hooks/use-all-experiments";
import * as useAllModelHooks from "../../../core/hooks/use-all-models";
import * as useAllPromptHooks from "../../../core/hooks/use-all-prompts";
import * as useUserGatewayEndpointPermissions from "../../../core/hooks/use-user-gateway-endpoint-permissions";
import * as useGroupGatewayEndpointPermissions from "../../../core/hooks/use-group-gateway-endpoint-permissions";
import * as useAllGatewayEndpoints from "../../../core/hooks/use-all-gateway-endpoints";
import type {
  PermissionType,
  ExperimentPermission,
  ModelPermission,
  ExperimentListItem,
} from "../../../shared/types/entity";
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
vi.mock("../../../core/hooks/use-search");
vi.mock("../../../core/hooks/use-user-experiment-permissions");
vi.mock("../../../core/hooks/use-user-model-permissions");
vi.mock("../../../core/hooks/use-user-prompt-permissions");
vi.mock("../../../core/hooks/use-group-experiment-permissions");
vi.mock("../../../core/hooks/use-group-model-permissions");
vi.mock("../../../core/hooks/use-group-prompt-permissions");
vi.mock("../../../core/hooks/use-all-experiments");
vi.mock("../../../core/hooks/use-all-models");
vi.mock("../../../core/hooks/use-all-prompts");
vi.mock("../../../core/hooks/use-user-gateway-endpoint-permissions");
vi.mock("../../../core/hooks/use-group-gateway-endpoint-permissions");
vi.mock("../../../core/hooks/use-all-gateway-endpoints");

describe("NormalPermissionsView", () => {
  const mockShowToast = vi.fn();
  const mockRefresh = vi.fn();

  const defaultSearch = {
    searchTerm: "",
    submittedTerm: "",
    handleInputChange: vi.fn(),
    handleSearchSubmit: vi.fn(),
    handleClearSearch: vi.fn(),
  };

  const mockExpPermissions: ExperimentPermission[] = [
    { name: "item1", permission: "READ", kind: "user", id: "id1" },
    { name: "item2", permission: "MANAGE", kind: "service-account", id: "id2" },
    { name: "fallback", permission: "READ", kind: "fallback", id: "f1" },
  ];

  const mockModelPermissions: ModelPermission[] = [
    { name: "item1", permission: "READ", kind: "user" },
    { name: "item2", permission: "MANAGE", kind: "service-account" },
    { name: "fallback", permission: "READ", kind: "fallback" },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as ToastContextType);
    vi.spyOn(useSearchModule, "useSearch").mockReturnValue(defaultSearch);

    // Default mock implementation for all hooks
    vi.spyOn(useExpHooks, "useUserExperimentPermissions").mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockExpPermissions,
    });
    vi.spyOn(
      useModelHooks,
      "useUserRegisteredModelPermissions",
    ).mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockModelPermissions,
    });
    vi.spyOn(usePromptHooks, "useUserPromptPermissions").mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockModelPermissions,
    });
    vi.spyOn(useGroupExpHooks, "useGroupExperimentPermissions").mockReturnValue(
      {
        isLoading: false,
        error: null,
        refresh: mockRefresh,
        permissions: mockExpPermissions,
      },
    );
    vi.spyOn(
      useGroupModelHooks,
      "useGroupRegisteredModelPermissions",
    ).mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockModelPermissions,
    });
    vi.spyOn(useGroupPromptHooks, "useGroupPromptPermissions").mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockModelPermissions,
    });

    vi.spyOn(useAllExpHooks, "useAllExperiments").mockReturnValue({
      allExperiments: [{ id: "new1", name: "New Exp" } as ExperimentListItem],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    vi.spyOn(useAllModelHooks, "useAllModels").mockReturnValue({
      allModels: [
        { name: "New Model", aliases: "", description: "", tags: {} },
      ],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    vi.spyOn(useAllPromptHooks, "useAllPrompts").mockReturnValue({
      allPrompts: [
        { name: "New Prompt", aliases: "", description: "", tags: {} },
      ],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    vi.spyOn(
      useUserGatewayEndpointPermissions,
      "useUserGatewayEndpointPermissions",
    ).mockReturnValue({
      permissions: mockExpPermissions,
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    });

    vi.spyOn(
      useGroupGatewayEndpointPermissions,
      "useGroupGatewayEndpointPermissions",
    ).mockReturnValue({
      permissions: mockExpPermissions,
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    });

    vi.spyOn(useAllGatewayEndpoints, "useAllGatewayEndpoints").mockReturnValue({
      allGatewayEndpoints: [
        {
          name: "New Endpoint",
          type: "llm/v1/chat",
          description: "",
          route_type: "llm/v1/chat",
          auth_type: "bearer",
        },
      ],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
  });

  const types: PermissionType[] = [
    "experiments",
    "models",
    "prompts",
    "endpoints",
  ];

  types.forEach((type) => {
    describe(`Type: ${type}`, () => {
      const getExpectedValue = (t: string) => {
        if (t === "experiments") return "new1";
        if (t === "models") return "New Model";
        if (t === "prompts") return "New Prompt";
        return "New Endpoint";
      };

      it(`renders table with data for ${type}`, () => {
        render(
          <NormalPermissionsView
            type={type}
            entityKind="user"
            entityName="user1"
          />,
        );
        expect(screen.getByText("item1")).toBeDefined();
      });

      it(`opens grant modal and saves for ${type} (group)`, async () => {
        vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
        render(
          <NormalPermissionsView
            type={type}
            entityKind="group"
            entityName="group1"
          />,
        );

        const addText =
          type === "experiments"
            ? /Add experiment/i
            : type === "models"
              ? /Add model/i
              : type === "prompts"
                ? /Add prompt/i
                : /Add endpoint/i;
        fireEvent.click(screen.getByText(addText));

        const labelText =
          type === "experiments"
            ? /Experiment/i
            : type === "models"
              ? /Model/i
              : type === "prompts"
                ? /Prompt/i
                : /Endpoint/i;
        const select = screen.getByLabelText(labelText);
        fireEvent.change(select, { target: { value: getExpectedValue(type) } });

        const saveButton = screen.getByRole("button", { name: /^Save$/i });
        fireEvent.click(saveButton);

        await waitFor(() => {
          expect(httpModule.http).toHaveBeenCalledWith(
            expect.stringContaining(
              `/api/2.0/mlflow/permissions/groups/group1/${type === "models" ? "registered-models" : type === "endpoints" ? "gateways/endpoints" : type}`,
            ),
            expect.objectContaining({ method: "POST" }),
          );
        });
      });

      it(`handles removing for ${type} (user)`, async () => {
        vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
        render(
          <NormalPermissionsView
            type={type}
            entityKind="user"
            entityName="user1"
          />,
        );

        const removeButtons = screen.getAllByTitle(/Remove permission/i);
        fireEvent.click(removeButtons[0]);

        await waitFor(() => {
          expect(httpModule.http).toHaveBeenCalledWith(
            expect.stringContaining(
              `/api/2.0/mlflow/permissions/users/user1/${type === "models" ? "registered-models" : type === "endpoints" ? "gateways/endpoints" : type}`,
            ),
            expect.objectContaining({ method: "DELETE" }),
          );
        });
      });
    });
  });

  it("verifies icon and action logic for different kinds", () => {
    // user kind on user entity
    render(
      <NormalPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );
    const editButtons = screen.getAllByTitle(/Edit permission/i);
    const addPermissionButtons = screen.getAllByTitle(/Add permission/i);
    const removeButtons = screen.getAllByTitle(/Remove permission/i);

    expect(editButtons[0]).toBeDefined(); // item1 (kind: user)
    expect(addPermissionButtons[0]).toBeDefined(); // fallback (kind: fallback)
    expect(removeButtons[0]).toBeEnabled(); // item1 (kind: user)
    expect(removeButtons[2]).toBeDisabled(); // fallback (kind: fallback)
  });

  it("handles failure during operations", async () => {
    vi.spyOn(httpModule, "http").mockRejectedValue(new Error("Fail"));
    render(
      <NormalPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );

    const removeButtons = screen.getAllByTitle(/Remove permission/i);
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.stringContaining("Failed"),
        "error",
      );
    });
  });

  it("prefixes URL with basePath from runtime config", async () => {
    vi.mocked(getRuntimeConfig).mockResolvedValue({
      basePath: "/mlflow",
      uiPath: "",
      provider: "",
      gen_ai_gateway_enabled: false,
      authenticated: true,
    });
    vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
    render(
      <NormalPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );

    const removeButtons = screen.getAllByTitle(/Remove permission/i);
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(httpModule.http).toHaveBeenCalledWith(
        expect.stringMatching(/^\/mlflow\//),
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  it("renders loading and error appropriately", () => {
    vi.spyOn(useExpHooks, "useUserExperimentPermissions").mockReturnValue({
      isLoading: true,
      error: null,
      refresh: mockRefresh,
      permissions: mockExpPermissions,
    });
    const { rerender } = render(
      <NormalPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );
    expect(screen.getByText(/Loading/i)).toBeDefined();

    vi.spyOn(useExpHooks, "useUserExperimentPermissions").mockReturnValue({
      isLoading: false,
      error: new Error("Error"),
      refresh: mockRefresh,
      permissions: mockExpPermissions,
    });
    rerender(
      <NormalPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );
    expect(screen.getByText(/Error/i)).toBeDefined();
  });
});
