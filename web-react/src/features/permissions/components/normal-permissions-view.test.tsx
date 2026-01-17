import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { NormalPermissionsView } from "./normal-permissions-view";

const mockHttp = vi.fn();
const mockShowToast = vi.fn();

vi.mock("../../../core/services/http", () => ({
  http: (...args: any[]) => mockHttp(...args),
}));

vi.mock("../../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

// Mock hooks
vi.mock("../../../core/hooks/use-user-experiment-permissions", () => ({
  useUserExperimentPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-user-model-permissions", () => ({
  useUserRegisteredModelPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-user-prompt-permissions", () => ({
  useUserPromptPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-group-experiment-permissions", () => ({
  useGroupExperimentPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-group-model-permissions", () => ({
  useGroupRegisteredModelPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-group-prompt-permissions", () => ({
  useGroupPromptPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));

vi.mock("../../../core/hooks/use-all-experiments", () => ({ useAllExperiments: () => ({ allExperiments: [] }) }));
vi.mock("../../../core/hooks/use-all-models", () => ({ useAllModels: () => ({ allModels: [] }) }));
vi.mock("../../../core/hooks/use-all-prompts", () => ({ useAllPrompts: () => ({ allPrompts: [] }) }));

vi.mock("../../../core/hooks/use-search", () => ({
  useSearch: () => ({
    searchTerm: "",
    submittedTerm: "",
    handleInputChange: vi.fn(),
    handleSearchSubmit: vi.fn(),
    handleClearSearch: vi.fn(),
  }),
}));

vi.mock("../../../shared/components/page/page-status", () => ({
    default: ({ isLoading }: any) => isLoading ? <div>Loading permissions...</div> : null
}));

vi.mock("../../../shared/components/entity-list-table", () => ({
    EntityListTable: () => <div data-testid="entity-list">Table</div>
}));

describe("NormalPermissionsView", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    })

  it("renders correctly", () => {
    render(<NormalPermissionsView type="experiments" entityKind="user" entityName="testuser" />);
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
  });
});
