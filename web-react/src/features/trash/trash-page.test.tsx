import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TrashPage from "./trash-page";
import { MemoryRouter, Route, Routes } from "react-router";
import * as trashService from "../../core/services/trash-service";
import * as useDeletedExperimentsModule from "../../core/hooks/use-deleted-experiments";
import * as useDeletedRunsModule from "../../core/hooks/use-deleted-runs";
import * as useSearchModule from "../../core/hooks/use-search";
import * as useToastModule from "../../shared/components/toast/use-toast";

vi.mock("../../core/services/trash-service");
vi.mock("../../core/hooks/use-deleted-experiments");
vi.mock("../../core/hooks/use-deleted-runs");
vi.mock("../../core/hooks/use-search");
vi.mock("../../shared/components/toast/use-toast");

describe("TrashPage", () => {
  const mockShowToast = vi.fn();
  const mockRefreshExp = vi.fn();
  const mockRefreshRuns = vi.fn();

  const mockExperiments = [
    {
      experiment_id: "exp1",
      name: "Exp 1",
      creation_time: 1000,
      last_update_time: 2000,
    },
    {
      experiment_id: "exp2",
      name: "Exp 2",
      creation_time: 3000,
      last_update_time: 4000,
    },
  ];

  const mockRuns = [
    {
      run_id: "run1",
      run_name: "Run 1",
      start_time: 1000,
      end_time: 2000,
      experiment_id: "exp1",
    },
  ];

  const defaultSearch = {
    searchTerm: "",
    submittedTerm: "",
    handleInputChange: vi.fn(),
    handleSearchSubmit: vi.fn(),
    handleClearSearch: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as unknown as ReturnType<typeof useToastModule.useToast>);
    vi.spyOn(useSearchModule, "useSearch").mockReturnValue(
      defaultSearch as unknown as ReturnType<typeof useSearchModule.useSearch>,
    );

    vi.spyOn(
      useDeletedExperimentsModule,
      "useDeletedExperiments",
    ).mockReturnValue({
      deletedExperiments: mockExperiments,
      isLoading: false,
      error: null,
      refresh: mockRefreshExp,
    } as unknown as ReturnType<
      typeof useDeletedExperimentsModule.useDeletedExperiments
    >);

    vi.spyOn(useDeletedRunsModule, "useDeletedRuns").mockReturnValue({
      deletedRuns: mockRuns,
      isLoading: false,
      error: null,
      refresh: mockRefreshRuns,
    } as unknown as ReturnType<typeof useDeletedRunsModule.useDeletedRuns>);
  });

  const renderWithRouter = (initialEntry = "/trash/experiments") => {
    return render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/trash/:tab" element={<TrashPage />} />
          <Route path="/trash" element={<TrashPage />} />
        </Routes>
      </MemoryRouter>,
    );
  };

  it("renders experiments tab by default", () => {
    renderWithRouter();
    expect(screen.getByText("Exp 1")).toBeDefined();
    expect(screen.getByText("Exp 2")).toBeDefined();
    expect(screen.queryByText("Run 1")).toBeNull();
  });

  it("renders runs tab when navigated", () => {
    renderWithRouter("/trash/runs");
    expect(screen.getByText("Run 1")).toBeDefined();
    expect(screen.queryByText("Exp 1")).toBeNull();
  });

  it("handles search submission", () => {
    renderWithRouter();
    const searchInput = screen.getByPlaceholderText(/Search experiments/i);
    fireEvent.change(searchInput, { target: { value: "test" } });
    fireEvent.submit(searchInput.closest("form")!);
    expect(defaultSearch.handleSearchSubmit).toHaveBeenCalled();
  });

  it("handles individual selection", () => {
    renderWithRouter();
    const checkboxes = screen.getAllByRole("checkbox");
    // checkboxes[0] is select-all, [1] is item1, [2] is item2
    fireEvent.click(checkboxes[1]);

    const restoreButtons = screen.getAllByRole("button", {
      name: /^Restore$/i,
    });
    const deleteButtons = screen.getAllByRole("button", { name: /^Delete$/i });

    expect(restoreButtons[0]).not.toBeDisabled();
    expect(deleteButtons[0]).not.toBeDisabled();
  });

  it("handles select all", () => {
    renderWithRouter();
    const selectAll = screen.getAllByRole("checkbox")[0];
    fireEvent.click(selectAll);

    const restoreButton = screen.getAllByRole("button", {
      name: /^Restore$/i,
    })[0];
    expect(restoreButton).not.toBeDisabled();
  });

  it("handles restoring an item", async () => {
    vi.spyOn(trashService, "restoreExperiment").mockResolvedValue(
      {} as unknown as { message: string },
    );
    renderWithRouter();

    const restoreIcons = screen.getAllByTitle("Restore");
    fireEvent.click(restoreIcons[0]);

    await waitFor(() => {
      expect(trashService.restoreExperiment).toHaveBeenCalledWith("exp1");
    });
    expect(mockShowToast).toHaveBeenCalledWith(
      expect.stringContaining("restored"),
      "success",
    );
    expect(mockRefreshExp).toHaveBeenCalled();
  });

  it("handles permanent deletion (single item)", async () => {
    vi.spyOn(trashService, "cleanupTrash").mockResolvedValue(
      {} as unknown as { message: string },
    );
    renderWithRouter();

    const deleteIcons = screen.getAllByTitle("Delete Permanently");
    fireEvent.click(deleteIcons[1]); // exp2

    expect(screen.getByText(/Remove from trash/i)).toBeDefined();
    expect(screen.getByText(/will be permanently deleted/i)).toBeDefined();

    // Use a more specific selector for the modal confirm button
    const confirmButton = screen
      .getByText("Delete Permanently", { selector: "button span" })
      .closest("button")!;
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(trashService.cleanupTrash).toHaveBeenCalledWith({
        experiment_ids: "exp2",
      });
    });
    expect(mockShowToast).toHaveBeenCalledWith(
      expect.stringContaining("deleted"),
      "success",
    );
  });

  it("handles bulk operations", async () => {
    vi.spyOn(trashService, "restoreExperiment").mockResolvedValue(
      {} as unknown as { message: string },
    );
    renderWithRouter();

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);
    fireEvent.click(checkboxes[2]);

    const restoreButton = screen.getAllByRole("button", {
      name: /^Restore$/i,
    })[0];
    fireEvent.click(restoreButton);

    await waitFor(() => {
      expect(trashService.restoreExperiment).toHaveBeenCalledTimes(2);
    });
  });

  it("handles errors during restore", async () => {
    vi.spyOn(trashService, "restoreExperiment").mockRejectedValue(
      new Error("Fail"),
    );
    renderWithRouter();

    const restoreIcons = screen.getAllByTitle("Restore");
    fireEvent.click(restoreIcons[0]);

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.stringContaining("Failed"),
        "error",
      );
    });
  });

  it("handles runs tab interactions", async () => {
    vi.spyOn(trashService, "restoreRun").mockResolvedValue(
      {} as unknown as { message: string },
    );
    renderWithRouter("/trash/runs");

    const restoreIcons = screen.getAllByTitle("Restore");
    fireEvent.click(restoreIcons[0]);

    await waitFor(() => {
      expect(trashService.restoreRun).toHaveBeenCalledWith("run1");
    });
    expect(mockRefreshRuns).toHaveBeenCalled();
  });

  it("renders loading and error states", () => {
    vi.spyOn(
      useDeletedExperimentsModule,
      "useDeletedExperiments",
    ).mockReturnValue({
      deletedExperiments: [],
      isLoading: true,
      error: null,
      refresh: mockRefreshExp,
    } as unknown as ReturnType<
      typeof useDeletedExperimentsModule.useDeletedExperiments
    >);

    const { unmount } = renderWithRouter();
    expect(screen.getByText(/Loading/i)).toBeDefined();
    unmount();

    vi.spyOn(
      useDeletedExperimentsModule,
      "useDeletedExperiments",
    ).mockReturnValue({
      deletedExperiments: [],
      isLoading: false,
      error: "Error",
      refresh: mockRefreshExp,
    } as unknown as ReturnType<
      typeof useDeletedExperimentsModule.useDeletedExperiments
    >);
    renderWithRouter();
    expect(screen.getByText(/Error/i)).toBeDefined();
  });
});
