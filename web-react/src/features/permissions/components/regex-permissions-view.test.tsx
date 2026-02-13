import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RegexPermissionsView } from "./regex-permissions-view";
import * as httpModule from "../../../core/services/http";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import * as useSearchModule from "../../../core/hooks/use-search";
import * as useExpHooks from "../../../core/hooks/use-user-experiment-pattern-permissions";
import * as useModelHooks from "../../../core/hooks/use-user-model-pattern-permissions";
import * as usePromptHooks from "../../../core/hooks/use-user-prompt-pattern-permissions";
import * as useGroupExpHooks from "../../../core/hooks/use-group-experiment-pattern-permissions";
import * as useGroupModelHooks from "../../../core/hooks/use-group-model-pattern-permissions";
import * as useGroupPromptHooks from "../../../core/hooks/use-group-prompt-pattern-permissions";
import * as useUserGatewayEndpointPatternPermissions from "../../../core/hooks/use-user-gateway-endpoint-pattern-permissions";
import * as useGroupGatewayEndpointPatternPermissions from "../../../core/hooks/use-group-gateway-endpoint-pattern-permissions";
import * as useUserGatewaySecretPatternPermissions from "../../../core/hooks/use-user-gateway-secret-pattern-permissions";
import * as useGroupGatewaySecretPatternPermissions from "../../../core/hooks/use-group-gateway-secret-pattern-permissions";
import * as useUserGatewayModelPatternPermissions from "../../../core/hooks/use-user-gateway-model-pattern-permissions";
import * as useGroupGatewayModelPatternPermissions from "../../../core/hooks/use-group-gateway-model-pattern-permissions";
import type {
  PermissionType,
  ExperimentPatternPermission,
  ModelPatternPermission,
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
vi.mock("../../../core/hooks/use-user-experiment-pattern-permissions");
vi.mock("../../../core/hooks/use-user-model-pattern-permissions");
vi.mock("../../../core/hooks/use-user-prompt-pattern-permissions");
vi.mock("../../../core/hooks/use-group-experiment-pattern-permissions");
vi.mock("../../../core/hooks/use-group-model-pattern-permissions");
vi.mock("../../../core/hooks/use-group-prompt-pattern-permissions");
vi.mock("../../../core/hooks/use-user-gateway-endpoint-pattern-permissions");
vi.mock("../../../core/hooks/use-group-gateway-endpoint-pattern-permissions");
vi.mock("../../../core/hooks/use-user-gateway-secret-pattern-permissions");
vi.mock("../../../core/hooks/use-group-gateway-secret-pattern-permissions");
vi.mock("../../../core/hooks/use-user-gateway-model-pattern-permissions");
vi.mock("../../../core/hooks/use-group-gateway-model-pattern-permissions");

describe("RegexPermissionsView", () => {
  const mockShowToast = vi.fn();
  const mockRefresh = vi.fn();

  const defaultSearch = {
    searchTerm: "",
    submittedTerm: "",
    handleInputChange: vi.fn(),
    handleSearchSubmit: vi.fn(),
    handleClearSearch: vi.fn(),
  };

  const mockExpPatternPermissions: ExperimentPatternPermission[] = [
    { regex: "^test_.*", permission: "READ", priority: 100, id: 1 },
    { regex: "^prod_.*", permission: "MANAGE", priority: 0, id: 2 },
  ];

  const mockModelPatternPermissions: ModelPatternPermission[] = [
    {
      regex: "^test_.*",
      permission: "READ",
      priority: 100,
      id: 1,
      prompt: false,
    },
    {
      regex: "^prod_.*",
      permission: "MANAGE",
      priority: 0,
      id: 2,
      prompt: false,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as ToastContextType);
    vi.spyOn(useSearchModule, "useSearch").mockReturnValue(defaultSearch);

    vi.spyOn(
      useExpHooks,
      "useUserExperimentPatternPermissions",
    ).mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockExpPatternPermissions,
    });
    vi.spyOn(useModelHooks, "useUserModelPatternPermissions").mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockModelPatternPermissions,
    });
    vi.spyOn(usePromptHooks, "useUserPromptPatternPermissions").mockReturnValue(
      {
        isLoading: false,
        error: null,
        refresh: mockRefresh,
        permissions: mockModelPatternPermissions,
      },
    );
    vi.spyOn(
      useGroupExpHooks,
      "useGroupExperimentPatternPermissions",
    ).mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockExpPatternPermissions,
    });
    vi.spyOn(
      useGroupModelHooks,
      "useGroupModelPatternPermissions",
    ).mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockModelPatternPermissions,
    });
    vi.spyOn(
      useGroupPromptHooks,
      "useGroupPromptPatternPermissions",
    ).mockReturnValue({
      isLoading: false,
      error: null,
      refresh: mockRefresh,
      permissions: mockModelPatternPermissions,
    });

    vi.spyOn(
      useUserGatewayEndpointPatternPermissions,
      "useUserGatewayEndpointPatternPermissions",
    ).mockReturnValue({
      permissions: mockExpPatternPermissions,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    vi.spyOn(
      useGroupGatewayEndpointPatternPermissions,
      "useGroupGatewayEndpointPatternPermissions",
    ).mockReturnValue({
      permissions: mockExpPatternPermissions,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    vi.spyOn(
      useUserGatewaySecretPatternPermissions,
      "useUserGatewaySecretPatternPermissions",
    ).mockReturnValue({
      permissions: mockExpPatternPermissions,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    vi.spyOn(
      useGroupGatewaySecretPatternPermissions,
      "useGroupGatewaySecretPatternPermissions",
    ).mockReturnValue({
      permissions: mockExpPatternPermissions,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    vi.spyOn(
      useUserGatewayModelPatternPermissions,
      "useUserGatewayModelPatternPermissions",
    ).mockReturnValue({
      permissions: mockExpPatternPermissions,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    vi.spyOn(
      useGroupGatewayModelPatternPermissions,
      "useGroupGatewayModelPatternPermissions",
    ).mockReturnValue({
      permissions: mockExpPatternPermissions,
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
    "ai-secrets",
    "ai-models",
  ];

  const getUrlPart = (type: PermissionType) => {
    if (type === "experiments") return "experiment-patterns";
    if (type === "models") return "registered-models-patterns";
    if (type === "prompts") return "prompts-patterns";
    if (type === "endpoints") return "gateways/endpoints-patterns";
    if (type === "ai-secrets") return "gateways/secrets-patterns";
    return "gateways/model-definitions-patterns";
  };

  types.forEach((type) => {
    describe(`Type: ${type}`, () => {
      it(`renders table with data for ${type} (user)`, () => {
        render(
          <RegexPermissionsView
            type={type}
            entityKind="user"
            entityName="user1"
          />,
        );
        expect(screen.getByText("^test_.*")).toBeDefined();
      });

      it(`renders table with data for ${type} (group)`, () => {
        render(
          <RegexPermissionsView
            type={type}
            entityKind="group"
            entityName="group1"
          />,
        );
        expect(screen.getByText("^test_.*")).toBeDefined();
      });

      it(`opens add modal and saves for ${type} (user)`, async () => {
        vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
        render(
          <RegexPermissionsView
            type={type}
            entityKind="user"
            entityName="user1"
          />,
        );

        fireEvent.click(screen.getByText(/Add Regex/i));

        const regexInput = screen.getByLabelText(/Regex\*/i);
        fireEvent.change(regexInput, { target: { value: "^new_.*" } });

        const saveButton = screen.getByRole("button", { name: /^Save$/i });
        fireEvent.click(saveButton);

        await waitFor(() => {
          expect(httpModule.http).toHaveBeenCalledWith(
            expect.stringContaining("/users/user1/"),
            expect.objectContaining({ method: "POST" }),
          );
        });
      });

      it(`opens add modal and saves for ${type} (group)`, async () => {
        vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
        render(
          <RegexPermissionsView
            type={type}
            entityKind="group"
            entityName="group1"
          />,
        );

        fireEvent.click(screen.getByText(/Add Regex/i));

        const regexInput = screen.getByLabelText(/Regex\*/i);
        fireEvent.change(regexInput, { target: { value: "^new_grp_.*" } });

        const saveButton = screen.getByRole("button", { name: /^Save$/i });
        fireEvent.click(saveButton);

        await waitFor(() => {
          expect(httpModule.http).toHaveBeenCalledWith(
            expect.stringContaining("/groups/group1/"),
            expect.objectContaining({ method: "POST" }),
          );
        });
      });

      it(`opens edit modal and saves for ${type}`, async () => {
        vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
        render(
          <RegexPermissionsView
            type={type}
            entityKind="user"
            entityName="user1"
          />,
        );

        const editButtons = screen.getAllByTitle(/Edit pattern permission/i);
        fireEvent.click(editButtons[0]);

        const saveButton = screen.getByRole("button", { name: /Ok/i });
        fireEvent.click(saveButton);

        await waitFor(() => {
          expect(httpModule.http).toHaveBeenCalledWith(
            expect.stringContaining(`${getUrlPart(type)}/1`),
            expect.objectContaining({ method: "PATCH" }),
          );
        });
      });

      it(`handles removing for ${type}`, async () => {
        vi.spyOn(httpModule, "http").mockResolvedValue({} as Response);
        render(
          <RegexPermissionsView
            type={type}
            entityKind="user"
            entityName="user1"
          />,
        );

        const removeButtons = screen.getAllByTitle(
          /Remove pattern permission/i,
        );
        fireEvent.click(removeButtons[0]);

        await waitFor(() => {
          expect(httpModule.http).toHaveBeenCalledWith(
            expect.stringContaining(`${getUrlPart(type)}/1`),
            expect.objectContaining({ method: "DELETE" }),
          );
        });
      });
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
      <RegexPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );

    const removeButtons = screen.getAllByTitle(/Remove pattern permission/i);
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(httpModule.http).toHaveBeenCalledWith(
        expect.stringMatching(/^\/mlflow\//),
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  it("renders loading and error", () => {
    vi.spyOn(
      useExpHooks,
      "useUserExperimentPatternPermissions",
    ).mockReturnValue({
      isLoading: true,
      error: null,
      refresh: mockRefresh,
      permissions: mockExpPatternPermissions,
    });
    const { rerender } = render(
      <RegexPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );
    expect(screen.getByText(/Loading/i)).toBeDefined();

    vi.spyOn(
      useExpHooks,
      "useUserExperimentPatternPermissions",
    ).mockReturnValue({
      isLoading: false,
      error: new Error("Fail"),
      refresh: mockRefresh,
      permissions: mockExpPatternPermissions,
    });
    rerender(
      <RegexPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );
    expect(screen.getByText(/Error/i)).toBeDefined();
  });

  it("clears search when type prop changes", () => {
    const { rerender } = render(
      <RegexPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );

    rerender(
      <RegexPermissionsView
        type="models"
        entityKind="user"
        entityName="user1"
      />,
    );

    expect(defaultSearch.handleClearSearch).toHaveBeenCalled();
  });
});
