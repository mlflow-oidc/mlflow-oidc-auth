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
import type { PermissionType } from "../../../shared/types/entity";

vi.mock("../../../core/services/http");
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

  const mockPermissions = [
    { name: "item1", permission: "READ", kind: "user", id: "id1" },
    { name: "item2", permission: "MANAGE", kind: "service-account", id: "id2" },
    { name: "fallback", permission: "READ", kind: "fallback" },
  ];

  const defaultHookResult = {
    isLoading: false,
    error: null,
    refresh: mockRefresh,
    permissions: mockPermissions,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
    } as any);
    vi.spyOn(useSearchModule, "useSearch").mockReturnValue(
      defaultSearch as any,
    );

    // Default mock implementation for all hooks
    vi.spyOn(useExpHooks, "useUserExperimentPermissions").mockReturnValue(
      defaultHookResult as any,
    );
    vi.spyOn(
      useModelHooks,
      "useUserRegisteredModelPermissions",
    ).mockReturnValue(defaultHookResult as any);
    vi.spyOn(usePromptHooks, "useUserPromptPermissions").mockReturnValue(
      defaultHookResult as any,
    );
    vi.spyOn(useGroupExpHooks, "useGroupExperimentPermissions").mockReturnValue(
      defaultHookResult as any,
    );
    vi.spyOn(
      useGroupModelHooks,
      "useGroupRegisteredModelPermissions",
    ).mockReturnValue(defaultHookResult as any);
    vi.spyOn(useGroupPromptHooks, "useGroupPromptPermissions").mockReturnValue(
      defaultHookResult as any,
    );

    vi.spyOn(useAllExpHooks, "useAllExperiments").mockReturnValue({
      allExperiments: [{ id: "new1", name: "New Exp" }],
    } as any);
    vi.spyOn(useAllModelHooks, "useAllModels").mockReturnValue({
      allModels: [{ name: "New Model" }],
    } as any);
    vi.spyOn(useAllPromptHooks, "useAllPrompts").mockReturnValue({
      allPrompts: [{ name: "New Prompt" }],
    } as any);
  });

  const types: PermissionType[] = ["experiments", "models", "prompts"];

  types.forEach((type) => {
    describe(`Type: ${type}`, () => {
      const getExpectedValue = (t: string) => {
        if (t === "experiments") return "new1";
        if (t === "models") return "New Model";
        return "New Prompt";
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
        vi.spyOn(httpModule, "http").mockResolvedValue({} as any);
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
              : /Add prompt/i;
        fireEvent.click(screen.getByText(addText));

        const labelText =
          type === "experiments"
            ? /Experiment/i
            : type === "models"
              ? /Model/i
              : /Prompt/i;
        const select = screen.getByLabelText(labelText);
        fireEvent.change(select, { target: { value: getExpectedValue(type) } });

        const saveButton = screen.getByRole("button", { name: /^Save$/i });
        fireEvent.click(saveButton);

        await waitFor(() => {
          expect(httpModule.http).toHaveBeenCalledWith(
            expect.stringContaining(
              `/api/2.0/mlflow/permissions/groups/group1/${type === "models" ? "registered-models" : type}`,
            ),
            expect.objectContaining({ method: "POST" }),
          );
        });
      });

      it(`handles removing for ${type} (user)`, async () => {
        vi.spyOn(httpModule, "http").mockResolvedValue({} as any);
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
              `/api/2.0/mlflow/permissions/users/user1/${type === "models" ? "registered-models" : type}`,
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

  it("renders loading and error appropriately", () => {
    vi.spyOn(useExpHooks, "useUserExperimentPermissions").mockReturnValue({
      ...defaultHookResult,
      isLoading: true,
    } as any);
    const { rerender } = render(
      <NormalPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );
    expect(screen.getByText(/Loading/i)).toBeDefined();

    vi.spyOn(useExpHooks, "useUserExperimentPermissions").mockReturnValue({
      ...defaultHookResult,
      error: "Error",
    } as any);
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
