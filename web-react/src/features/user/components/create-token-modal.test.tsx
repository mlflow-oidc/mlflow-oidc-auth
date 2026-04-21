import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CreateTokenModal } from "./create-token-modal";

// Mock the token service
const mockCreateUserToken = vi.fn();
vi.mock("../../../core/services/token-service", () => ({
  createUserToken: (data: { name: string; expiration: string }) =>
    mockCreateUserToken(data) as Promise<{
      id: number;
      name: string;
      token: string;
      message: string;
    }>,
}));

// Mock toast
const mockShowToast = vi.fn();
vi.mock("../../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

// Mock clipboard
const mockClipboard = {
  writeText: vi.fn(),
};

describe("CreateTokenModal", () => {
  const mockOnClose = vi.fn();
  const mockOnTokenCreated = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, { clipboard: mockClipboard });
    mockClipboard.writeText.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderModal = (isOpen = true) => {
    return render(
      <CreateTokenModal
        isOpen={isOpen}
        onClose={mockOnClose}
        onTokenCreated={mockOnTokenCreated}
      />
    );
  };

  describe("rendering", () => {
    it("renders modal when open", () => {
      renderModal(true);
      expect(screen.getByText("Create New Token")).toBeInTheDocument();
    });

    it("renders token name input", () => {
      renderModal();
      expect(screen.getByLabelText(/Token Name/i)).toBeInTheDocument();
    });

    it("renders expiration date input", () => {
      renderModal();
      expect(screen.getByLabelText(/Expiration Date/i)).toBeInTheDocument();
    });

    it("renders Cancel and Create Token buttons", () => {
      renderModal();
      expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Create Token/i })).toBeInTheDocument();
    });

    it("sets default expiration date to 1 year from now", () => {
      renderModal();
      const expirationInput =
        screen.getByLabelText<HTMLInputElement>(/Expiration Date/i);
      const maxDate = new Date(new Date().setFullYear(new Date().getFullYear() + 1))
        .toISOString()
        .split("T")[0];
      expect(expirationInput.value).toBe(maxDate);
    });
  });

  describe("form validation", () => {
    it("disables Create Token button when token name is empty", () => {
      renderModal();
      const createButton = screen.getByRole("button", { name: /Create Token/i });
      expect(createButton).toBeDisabled();
    });

    it("enables Create Token button when token name is provided", () => {
      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "my-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      expect(createButton).not.toBeDisabled();
    });

    it("keeps button disabled when token name is only whitespace", () => {
      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "   " } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      expect(createButton).toBeDisabled();
    });
  });

  describe("token creation", () => {
    it("calls createUserToken with correct data", async () => {
      mockCreateUserToken.mockResolvedValue({
        id: 1,
        name: "test-token",
        token: "secret-token-value",
        message: "Token created successfully",
      });

      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(mockCreateUserToken).toHaveBeenCalled();
        const callArgs = mockCreateUserToken.mock.calls[0][0] as {
          name: string;
          expiration: string;
        };
        expect(callArgs.name).toBe("test-token");
        expect(callArgs.expiration).toMatch(/^\d{4}-\d{2}-\d{2}T/);
      });
    });

    it("shows success toast after token creation", async () => {
      mockCreateUserToken.mockResolvedValue({
        id: 1,
        name: "test-token",
        token: "secret-token-value",
        message: "Token created successfully",
      });

      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith(
          "Token 'test-token' created successfully!",
          "success"
        );
      });
    });

    it("calls onTokenCreated callback after successful creation", async () => {
      mockCreateUserToken.mockResolvedValue({
        id: 1,
        name: "test-token",
        token: "secret-token-value",
        message: "Token created successfully",
      });

      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(mockOnTokenCreated).toHaveBeenCalled();
      });
    });

    it("displays access token after creation", async () => {
      mockCreateUserToken.mockResolvedValue({
        id: 1,
        name: "test-token",
        token: "secret-token-value",
        message: "Token created successfully",
      });

      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(screen.getByDisplayValue("secret-token-value")).toBeInTheDocument();
      });
    });

    it("shows loading state while creating", () => {
      mockCreateUserToken.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      );

      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      expect(screen.getByText("Creating...")).toBeInTheDocument();
    });
  });

  describe("error handling", () => {
    it("shows error toast when creation fails", async () => {
      mockCreateUserToken.mockRejectedValue(new Error("Network error"));

      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith("Network error", "error");
      });
    });

    it("shows duplicate error toast when token name already exists", async () => {
      mockCreateUserToken.mockRejectedValue(
        new Error("Token with name 'test-token' already exists")
      );

      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith(
          "Token with name 'test-token' already exists",
          "error"
        );
      });
    });
  });

  describe("token display and copy", () => {
    beforeEach(() => {
      mockCreateUserToken.mockResolvedValue({
        id: 1,
        name: "test-token",
        token: "secret-token-value",
        message: "Token created successfully",
      });
    });

    it("shows Done button after token is created", async () => {
      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Done/i })).toBeInTheDocument();
      });
    });

    it("disables input fields after token is created", async () => {
      renderModal();
      const nameInput = screen.getByLabelText<HTMLInputElement>(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(nameInput).toBeDisabled();
        expect(screen.getByLabelText(/Expiration Date/i)).toBeDisabled();
      });
    });

    it("copies token to clipboard when copy button is clicked", async () => {
      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(screen.getByDisplayValue("secret-token-value")).toBeInTheDocument();
      });

      const copyButton = screen.getByTitle("Copy Access Token");
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(mockClipboard.writeText).toHaveBeenCalledWith("secret-token-value");
      });
    });
  });

  describe("modal interactions", () => {
    it("calls onClose when Cancel is clicked", () => {
      renderModal();
      const cancelButton = screen.getByRole("button", { name: /Cancel/i });
      fireEvent.click(cancelButton);

      expect(mockOnClose).toHaveBeenCalled();
    });

    it("calls onClose when Done is clicked after token creation", async () => {
      mockCreateUserToken.mockResolvedValue({
        id: 1,
        name: "test-token",
        token: "secret-token-value",
        message: "Token created successfully",
      });

      renderModal();
      const nameInput = screen.getByLabelText(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Done/i })).toBeInTheDocument();
      });

      const doneButton = screen.getByRole("button", { name: /Done/i });
      fireEvent.click(doneButton);

      expect(mockOnClose).toHaveBeenCalled();
    });

    it("resets form when modal is closed", async () => {
      mockCreateUserToken.mockResolvedValue({
        id: 1,
        name: "test-token",
        token: "secret-token-value",
        message: "Token created successfully",
      });

      const { rerender } = renderModal();
      const nameInput = screen.getByLabelText<HTMLInputElement>(/Token Name/i);
      fireEvent.change(nameInput, { target: { value: "test-token" } });

      const createButton = screen.getByRole("button", { name: /Create Token/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(screen.getByDisplayValue("secret-token-value")).toBeInTheDocument();
      });

      // Close and reopen modal
      const doneButton = screen.getByRole("button", { name: /Done/i });
      fireEvent.click(doneButton);

      // Rerender with isOpen=true to simulate reopening
      rerender(
        <CreateTokenModal
          isOpen={true}
          onClose={mockOnClose}
          onTokenCreated={mockOnTokenCreated}
        />
      );

      // Form should be reset
      const newNameInput = screen.getByLabelText<HTMLInputElement>(/Token Name/i);
      expect(newNameInput.value).toBe("");
    });
  });
});
