import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { RegexPermissionsView } from "./regex-permissions-view";

const mockHttp = vi.fn();
const mockShowToast = vi.fn();

vi.mock("../../../core/services/http", () => ({
  http: (...args: any[]) => mockHttp(...args),
}));

vi.mock("../../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

// Mock hooks
vi.mock("../../../core/hooks/use-user-experiment-pattern-permissions", () => ({
  useUserExperimentPatternPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-user-model-pattern-permissions", () => ({
  useUserModelPatternPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-user-prompt-pattern-permissions", () => ({
  useUserPromptPatternPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-group-experiment-pattern-permissions", () => ({
  useGroupExperimentPatternPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-group-model-pattern-permissions", () => ({
  useGroupModelPatternPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));
vi.mock("../../../core/hooks/use-group-prompt-pattern-permissions", () => ({
  useGroupPromptPatternPermissions: () => ({ permissions: [], isLoading: false, refresh: vi.fn() }),
}));

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

vi.mock("./add-regex-rule-modal", () => ({
    AddRegexRuleModal: () => <div data-testid="add-regex-modal" />
}));

describe("RegexPermissionsView", () => {
  it("renders correctly", () => {
    render(<RegexPermissionsView type="experiments" entityKind="user" entityName="testuser" />);
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
    expect(screen.getAllByText("Add Regex")).toHaveLength(1);
  });
});
