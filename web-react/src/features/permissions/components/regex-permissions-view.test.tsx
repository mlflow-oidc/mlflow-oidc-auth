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
import type { PermissionType } from "../../../shared/types/entity";

vi.mock("../../../core/services/http");
vi.mock("../../../shared/components/toast/use-toast");
vi.mock("../../../core/hooks/use-search");
vi.mock("../../../core/hooks/use-user-experiment-pattern-permissions");
vi.mock("../../../core/hooks/use-user-model-pattern-permissions");
vi.mock("../../../core/hooks/use-user-prompt-pattern-permissions");
vi.mock("../../../core/hooks/use-group-experiment-pattern-permissions");
vi.mock("../../../core/hooks/use-group-model-pattern-permissions");
vi.mock("../../../core/hooks/use-group-prompt-pattern-permissions");

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

  const mockPermissions = [
    { regex: "^test_.*", permission: "READ", priority: 100, id: 1 },
    { regex: "^prod_.*", permission: "MANAGE", priority: 0, id: 2 },
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

    vi.spyOn(
      useExpHooks,
      "useUserExperimentPatternPermissions",
    ).mockReturnValue(defaultHookResult as any);
    vi.spyOn(useModelHooks, "useUserModelPatternPermissions").mockReturnValue(
      defaultHookResult as any,
    );
    vi.spyOn(usePromptHooks, "useUserPromptPatternPermissions").mockReturnValue(
      defaultHookResult as any,
    );
    vi.spyOn(
      useGroupExpHooks,
      "useGroupExperimentPatternPermissions",
    ).mockReturnValue(defaultHookResult as any);
    vi.spyOn(
      useGroupModelHooks,
      "useGroupModelPatternPermissions",
    ).mockReturnValue(defaultHookResult as any);
    vi.spyOn(
      useGroupPromptHooks,
      "useGroupPromptPatternPermissions",
    ).mockReturnValue(defaultHookResult as any);
  });

  const types: PermissionType[] = ["experiments", "models", "prompts"];

  const getUrlPart = (type: PermissionType) => {
    if (type === "experiments") return "experiment-patterns";
    if (type === "models") return "registered-models-patterns";
    return "prompts-patterns";
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
        vi.spyOn(httpModule, "http").mockResolvedValue({} as any);
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
        vi.spyOn(httpModule, "http").mockResolvedValue({} as any);
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
        vi.spyOn(httpModule, "http").mockResolvedValue({} as any);
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
        vi.spyOn(httpModule, "http").mockResolvedValue({} as any);
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

  it("renders loading and error", () => {
    vi.spyOn(
      useExpHooks,
      "useUserExperimentPatternPermissions",
    ).mockReturnValue({ ...defaultHookResult, isLoading: true } as any);
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
    ).mockReturnValue({ ...defaultHookResult, error: "Fail" } as any);
    rerender(
      <RegexPermissionsView
        type="experiments"
        entityKind="user"
        entityName="user1"
      />,
    );
    expect(screen.getByText(/Error/i)).toBeDefined();
  });
});
