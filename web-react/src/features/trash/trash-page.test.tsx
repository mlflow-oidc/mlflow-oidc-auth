import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import TrashPage from "./trash-page";

const mockUseDeletedExperiments = vi.fn();
const mockUseDeletedRuns = vi.fn();
const mockRestoreExperiment = vi.fn();
const mockRestoreRun = vi.fn();
const mockCleanupTrash = vi.fn();
const mockShowToast = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => ({ tab: "experiments" }),
  Link: ({ children, to, className }: any) => <a href={to} className={className}>{children}</a>,
}));

vi.mock("../../core/hooks/use-deleted-experiments", () => ({
  useDeletedExperiments: () => mockUseDeletedExperiments(),
}));

vi.mock("../../core/hooks/use-deleted-runs", () => ({
  useDeletedRuns: () => mockUseDeletedRuns(),
}));

vi.mock("../../core/services/trash-service", () => ({
  restoreExperiment: (...args: any[]) => mockRestoreExperiment(...args),
  restoreRun: (...args: any[]) => mockRestoreRun(...args),
  cleanupTrash: (...args: any[]) => mockCleanupTrash(...args),
}));

vi.mock("../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="page-container" title={title}>{children}</div>
  ),
}));

vi.mock("../../shared/components/page/page-status", () => ({
  default: ({ isLoading }: any) => isLoading ? <div>Loading...</div> : null
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => ({
    searchTerm: "",
    submittedTerm: "",
    handleInputChange: vi.fn(),
    handleSearchSubmit: vi.fn(),
    handleClearSearch: vi.fn(),
  }),
}));

vi.mock("../../shared/components/entity-list-table", () => ({
    EntityListTable: ({ data, columns }: any) => (
        <div data-testid="trash-list">
            {data.map((item: any) => (
                <div key={item.id} data-testid="trash-item">
                    {item.name}
                    {columns.find((c: any) => c.header === "Actions")?.render(item)}
                    {/* Render checkbox for testing selection */}
                    {columns.find((c: any) => c.id === "select")?.render(item)}
                </div>
            ))}
        </div>
    )
}));

vi.mock("../../shared/components/icon-button", () => ({
  IconButton: ({ title, onClick }: any) => <button onClick={onClick} title={title}>{title}</button>
}));

describe("TrashPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDeletedExperiments.mockReturnValue({
        deletedExperiments: [{ experiment_id: "1", name: "Exp 1", creation_time: 123, last_update_time: 456 }],
        isLoading: false,
        error: null,
        refresh: vi.fn(),
    });
    mockUseDeletedRuns.mockReturnValue({
        deletedRuns: [],
        isLoading: false,
        error: null,
        refresh: vi.fn(),
    });
  });

  it("renders deleted experiments", () => {
    render(<TrashPage />);
    expect(screen.getByText("Exp 1")).toBeInTheDocument();
  });

  it("calls restore when button clicked", async () => {
    mockRestoreExperiment.mockResolvedValue({});
    render(<TrashPage />);
    
    const restoreBtn = screen.getByTitle("Restore");
    fireEvent.click(restoreBtn);
    
    await waitFor(() => {
        expect(mockRestoreExperiment).toHaveBeenCalledWith("1");
    });
  });
});
