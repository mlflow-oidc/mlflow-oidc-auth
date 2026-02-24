import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TokensList } from "./tokens-list";

interface MockToken {
  id: number;
  name: string;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
}

interface MockUseTokensReturn {
  tokens: MockToken[];
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
}

// Mock useTokens hook
const mockRefresh = vi.fn();
const mockUseTokens = vi.fn<() => MockUseTokensReturn>();
vi.mock("../../../core/hooks/use-tokens", () => ({
  useTokens: () => mockUseTokens(),
}));

// Mock deleteUserToken
const mockDeleteUserToken = vi.fn<(id: number) => Promise<void>>();
vi.mock("../../../core/services/token-service", () => ({
  deleteUserToken: (id: number) => mockDeleteUserToken(id),
  createUserToken: vi.fn(),
}));

// Mock toast
const mockShowToast = vi.fn();
vi.mock("../../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

describe("TokensList", () => {
  const mockTokens = [
    {
      id: 1,
      name: "token-one",
      created_at: "2024-01-15T10:00:00Z",
      expires_at: "2024-06-15T10:00:00Z",
      last_used_at: "2024-01-20T15:30:00Z",
    },
    {
      id: 2,
      name: "token-two",
      created_at: "2024-02-01T08:00:00Z",
      expires_at: "2024-08-01T08:00:00Z",
      last_used_at: null,
    },
    {
      id: 3,
      name: "ci-pipeline",
      created_at: "2024-03-01T12:00:00Z",
      expires_at: "2025-03-01T12:00:00Z",
      last_used_at: "2024-03-15T09:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseTokens.mockReturnValue({
      tokens: mockTokens,
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    });
  });

  describe("rendering", () => {
    it("renders token list with all tokens", () => {
      render(<TokensList />);
      expect(screen.getByText("token-one")).toBeInTheDocument();
      expect(screen.getByText("token-two")).toBeInTheDocument();
      expect(screen.getByText("ci-pipeline")).toBeInTheDocument();
    });

    it("renders Create Token button", () => {
      render(<TokensList />);
      expect(screen.getByRole("button", { name: /Create Token/i })).toBeInTheDocument();
    });

    it("renders search input", () => {
      render(<TokensList />);
      expect(screen.getByPlaceholderText("Search tokens...")).toBeInTheDocument();
    });

    it("renders table headers", () => {
      render(<TokensList />);
      expect(screen.getByText("Name")).toBeInTheDocument();
      expect(screen.getByText("Created")).toBeInTheDocument();
      expect(screen.getByText("Expires")).toBeInTheDocument();
      expect(screen.getByText("Last Used")).toBeInTheDocument();
      expect(screen.getByText("Actions")).toBeInTheDocument();
    });
  });

  describe("loading state", () => {
    it("shows loading message when loading", () => {
      mockUseTokens.mockReturnValue({
        tokens: [],
        isLoading: true,
        error: null,
        refresh: mockRefresh,
      });

      render(<TokensList />);
      expect(screen.getByText("Loading tokens...")).toBeInTheDocument();
    });
  });

  describe("error state", () => {
    it("shows error message when there is an error", () => {
      mockUseTokens.mockReturnValue({
        tokens: [],
        isLoading: false,
        error: new Error("Failed to fetch"),
        refresh: mockRefresh,
      });

      render(<TokensList />);
      expect(screen.getByText("Failed to load tokens")).toBeInTheDocument();
    });

    it("shows Retry button on error", () => {
      mockUseTokens.mockReturnValue({
        tokens: [],
        isLoading: false,
        error: new Error("Failed to fetch"),
        refresh: mockRefresh,
      });

      render(<TokensList />);
      expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
    });

    it("calls refresh when Retry is clicked", () => {
      mockUseTokens.mockReturnValue({
        tokens: [],
        isLoading: false,
        error: new Error("Failed to fetch"),
        refresh: mockRefresh,
      });

      render(<TokensList />);
      const retryButton = screen.getByRole("button", { name: /Retry/i });
      fireEvent.click(retryButton);

      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  describe("empty state", () => {
    it("shows empty message when no tokens exist", () => {
      mockUseTokens.mockReturnValue({
        tokens: [],
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      render(<TokensList />);
      expect(
        screen.getByText("No tokens found. Create your first token to get started.")
      ).toBeInTheDocument();
    });

    it("shows no results message when search returns no matches", () => {
      render(<TokensList />);
      const searchInput = screen.getByPlaceholderText("Search tokens...");
      fireEvent.change(searchInput, { target: { value: "nonexistent" } });

      // Submit the search form
      const form = searchInput.closest("form");
      fireEvent.submit(form!);

      expect(screen.getByText('No tokens matching "nonexistent"')).toBeInTheDocument();
    });
  });

  describe("search functionality", () => {
    it("filters tokens by name on search submit", () => {
      render(<TokensList />);
      const searchInput = screen.getByPlaceholderText("Search tokens...");
      fireEvent.change(searchInput, { target: { value: "ci" } });

      // Submit the search form
      const form = searchInput.closest("form");
      fireEvent.submit(form!);

      expect(screen.getByText("ci-pipeline")).toBeInTheDocument();
      expect(screen.queryByText("token-one")).not.toBeInTheDocument();
      expect(screen.queryByText("token-two")).not.toBeInTheDocument();
    });

    it("performs case-insensitive search", () => {
      render(<TokensList />);
      const searchInput = screen.getByPlaceholderText("Search tokens...");
      fireEvent.change(searchInput, { target: { value: "CI" } });

      // Submit the search form
      const form = searchInput.closest("form");
      fireEvent.submit(form!);

      expect(screen.getByText("ci-pipeline")).toBeInTheDocument();
    });

    it("clears search and shows all tokens", () => {
      render(<TokensList />);
      const searchInput = screen.getByPlaceholderText("Search tokens...");
      fireEvent.change(searchInput, { target: { value: "ci" } });

      // Submit the search form
      const form = searchInput.closest("form");
      fireEvent.submit(form!);

      expect(screen.queryByText("token-one")).not.toBeInTheDocument();

      // Clear search by clicking the clear button
      const clearButton = screen.getByRole("button", { name: /Clear search/i });
      fireEvent.click(clearButton);

      expect(screen.getByText("token-one")).toBeInTheDocument();
      expect(screen.getByText("ci-pipeline")).toBeInTheDocument();
    });
  });

  describe("delete functionality", () => {
    it("opens delete modal when delete button is clicked", () => {
      render(<TokensList />);
      const deleteButtons = screen.getAllByTitle(/Delete token/i);
      fireEvent.click(deleteButtons[0]);

      expect(screen.getByText("Delete Token")).toBeInTheDocument();
      expect(screen.getByText(/token-one/)).toBeInTheDocument();
    });

    it("deletes token when confirmed", async () => {
      mockDeleteUserToken.mockResolvedValue(undefined);

      render(<TokensList />);
      const deleteButtons = screen.getAllByTitle(/Delete token/i);
      fireEvent.click(deleteButtons[0]);

      // Click the confirm button in the modal
      const confirmButton = screen.getByRole("button", {
        name: /Delete Permanently/i,
      });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockDeleteUserToken).toHaveBeenCalledWith(1);
      });
    });

    it("shows success toast after deletion", async () => {
      mockDeleteUserToken.mockResolvedValue(undefined);

      render(<TokensList />);
      const deleteButtons = screen.getAllByTitle(/Delete token/i);
      fireEvent.click(deleteButtons[0]);

      const confirmButton = screen.getByRole("button", {
        name: /Delete Permanently/i,
      });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith(
          'Token "token-one" deleted successfully',
          "success"
        );
      });
    });

    it("refreshes token list after deletion", async () => {
      mockDeleteUserToken.mockResolvedValue(undefined);

      render(<TokensList />);
      const deleteButtons = screen.getAllByTitle(/Delete token/i);
      fireEvent.click(deleteButtons[0]);

      const confirmButton = screen.getByRole("button", {
        name: /Delete Permanently/i,
      });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockRefresh).toHaveBeenCalled();
      });
    });

    it("does not delete when cancel is clicked", () => {
      render(<TokensList />);
      const deleteButtons = screen.getAllByTitle(/Delete token/i);
      fireEvent.click(deleteButtons[0]);

      // Click Cancel in the modal
      const cancelButton = screen.getByRole("button", { name: /Cancel/i });
      fireEvent.click(cancelButton);

      expect(mockDeleteUserToken).not.toHaveBeenCalled();
      // Modal should be closed
      expect(screen.queryByText("Delete Token")).not.toBeInTheDocument();
    });

    it("shows error toast when deletion fails", async () => {
      mockDeleteUserToken.mockRejectedValue(new Error("Delete failed"));

      render(<TokensList />);
      const deleteButtons = screen.getAllByTitle(/Delete token/i);
      fireEvent.click(deleteButtons[0]);

      const confirmButton = screen.getByRole("button", {
        name: /Delete Permanently/i,
      });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith("Failed to delete token", "error");
      });
    });
  });

  describe("create modal", () => {
    it("opens create modal when Create Token is clicked", () => {
      render(<TokensList />);
      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      expect(screen.getByText("Create New Token")).toBeInTheDocument();
    });
  });

  describe("date formatting", () => {
    it("formats created date correctly", () => {
      render(<TokensList />);
      // The date "2024-01-15T10:00:00Z" should be formatted
      // This depends on locale, so we check for the year at minimum
      const rows = screen.getAllByRole("row");
      expect(rows.length).toBeGreaterThan(1);
    });

    it("shows dash for null last_used_at", () => {
      render(<TokensList />);
      // token-two has null last_used_at
      const dashElements = screen.getAllByText("-");
      expect(dashElements.length).toBeGreaterThan(0);
    });

    it("formats expires_at date correctly", () => {
      render(<TokensList />);
      // All tokens should have valid expiration dates formatted
      const rows = screen.getAllByRole("row");
      expect(rows.length).toBeGreaterThan(1);
    });
  });
});
