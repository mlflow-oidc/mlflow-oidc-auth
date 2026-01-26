import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ModelsPage from "./models-page";

import type { ModelListItem } from "../../shared/types/entity";
import type { Mock } from "vitest";

const mockUseAllModels: Mock<
  () => {
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
    allModels: ModelListItem[] | null;
  }
> = vi.fn();

const mockUseSearch: Mock<
  () => {
    searchTerm: string;
    submittedTerm: string;
    handleInputChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    handleSearchSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
    handleClearSearch: () => void;
  }
> = vi.fn();

vi.mock("../../core/hooks/use-all-models", () => ({
  useAllModels: () => mockUseAllModels(),
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => mockUseSearch(),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({
    children,
    title,
  }: {
    children: React.ReactNode;
    title: string;
  }) => (
    <div data-testid="page-container" title={title}>
      {children}
    </div>
  ),
}));

vi.mock("../../shared/components/page/page-status", () => ({
  default: ({
    isLoading,
    error,
  }: {
    isLoading: boolean;
    error: Error | null;
  }) => {
    if (isLoading) return <div>Loading...</div>;
    if (error) return <div>Error</div>;
    return null;
  },
}));

vi.mock("../../shared/components/search-input", () => ({
  SearchInput: () => <div data-testid="search-input" />,
}));

vi.mock("../../shared/components/entity-list-table", () => ({
  EntityListTable: ({ data }: { data: ModelListItem[] }) => (
    <div data-testid="entity-list">
      {data.map((item) => (
        <div key={item.name}>{item.name}</div>
      ))}
    </div>
  ),
}));

vi.mock("../../shared/components/row-action-button", () => ({
  RowActionButton: () => <button>Manage permissions</button>,
}));

describe("ModelsPage", () => {
  beforeEach(() => {
    mockUseSearch.mockReturnValue({
      searchTerm: "",
      submittedTerm: "",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });
    mockUseAllModels.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allModels: [],
    });
  });

  it("renders correctly with models", () => {
    mockUseAllModels.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allModels: [
        { name: "Model A", aliases: "", description: "", tags: {} },
        { name: "Model B", aliases: "", description: "", tags: {} },
      ],
    });

    render(<ModelsPage />);

    expect(screen.getByText("Model A")).toBeInTheDocument();
    expect(screen.getByText("Model B")).toBeInTheDocument();
  });
});
