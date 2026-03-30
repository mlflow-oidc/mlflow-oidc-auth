import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  CreateWorkspaceModal,
  validateWorkspaceName,
} from "./create-workspace-modal";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import * as workspaceServiceModule from "../../../core/services/workspace-service";

vi.mock("../../../shared/components/toast/use-toast");
vi.mock("../../../core/services/workspace-service");

describe("validateWorkspaceName", () => {
  it("returns error for empty name", () => {
    expect(validateWorkspaceName("")).toBe("Workspace name is required");
  });

  it("returns error for name shorter than 2 characters", () => {
    expect(validateWorkspaceName("a")).toBe(
      "Name must be at least 2 characters",
    );
  });

  it("returns error for name longer than 63 characters", () => {
    const longName = "a".repeat(64);
    expect(validateWorkspaceName(longName)).toBe(
      "Name must be at most 63 characters",
    );
  });

  it("returns error for name with uppercase letters", () => {
    expect(validateWorkspaceName("MyWorkspace")).toBe(
      "Name must be DNS-safe: lowercase letters, digits, hyphens; must start and end with alphanumeric",
    );
  });

  it("returns error for name starting with hyphen", () => {
    expect(validateWorkspaceName("-test")).toBe(
      "Name must be DNS-safe: lowercase letters, digits, hyphens; must start and end with alphanumeric",
    );
  });

  it("returns error for name ending with hyphen", () => {
    expect(validateWorkspaceName("test-")).toBe(
      "Name must be DNS-safe: lowercase letters, digits, hyphens; must start and end with alphanumeric",
    );
  });

  it("returns error for name with spaces", () => {
    expect(validateWorkspaceName("my workspace")).toBe(
      "Name must be DNS-safe: lowercase letters, digits, hyphens; must start and end with alphanumeric",
    );
  });

  it("returns error for reserved name 'default'", () => {
    expect(validateWorkspaceName("default")).toBe("This name is reserved");
  });

  it("returns null for valid name", () => {
    expect(validateWorkspaceName("my-workspace")).toBeNull();
  });

  it("returns null for valid name with digits", () => {
    expect(validateWorkspaceName("ws-123")).toBeNull();
  });

  it("returns null for two-character name", () => {
    expect(validateWorkspaceName("ab")).toBeNull();
  });
});

describe("CreateWorkspaceModal", () => {
  const mockShowToast = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as unknown as ReturnType<typeof useToastModule.useToast>);
  });

  it("renders correctly when open", () => {
    render(
      <CreateWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />,
    );

    expect(screen.getByText("Create Workspace")).toBeInTheDocument();
    expect(screen.getByLabelText("Name*")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toBeInTheDocument();
    expect(screen.getByLabelText("Default Artifact Root")).toBeInTheDocument();
  });

  it("validates name on input change", () => {
    render(
      <CreateWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />,
    );

    const nameInput = screen.getByLabelText("Name*");
    fireEvent.change(nameInput, { target: { value: "A" } });

    expect(
      screen.getByText("Name must be at least 2 characters"),
    ).toBeInTheDocument();
  });

  it("disables submit when name is invalid", () => {
    render(
      <CreateWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />,
    );

    const nameInput = screen.getByLabelText("Name*");
    fireEvent.change(nameInput, { target: { value: "AB" } });

    const createButton = screen.getByRole("button", { name: "Create" });
    expect(createButton).toBeDisabled();
  });

  it("enables submit when name is valid", () => {
    render(
      <CreateWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />,
    );

    const nameInput = screen.getByLabelText("Name*");
    fireEvent.change(nameInput, { target: { value: "my-workspace" } });

    const createButton = screen.getByRole("button", { name: "Create" });
    expect(createButton).not.toBeDisabled();
  });

  it("calls createWorkspace and onSuccess on successful submission", async () => {
    const mockCreateWorkspace = vi.spyOn(
      workspaceServiceModule,
      "createWorkspace",
    );
    mockCreateWorkspace.mockResolvedValue({
      name: "test-ws",
      description: "",
      default_artifact_root: null,
    });

    render(
      <CreateWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />,
    );

    fireEvent.change(screen.getByLabelText("Name*"), {
      target: { value: "test-ws" },
    });
    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(mockCreateWorkspace).toHaveBeenCalledWith({
        name: "test-ws",
        description: undefined,
        default_artifact_root: undefined,
      });
      expect(mockShowToast).toHaveBeenCalledWith(
        "Workspace created successfully",
        "success",
      );
      expect(mockOnSuccess).toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it("passes default_artifact_root when provided", async () => {
    const mockCreateWorkspace = vi.spyOn(
      workspaceServiceModule,
      "createWorkspace",
    );
    mockCreateWorkspace.mockResolvedValue({
      name: "test-ws",
      description: "desc",
      default_artifact_root: "s3://my-bucket",
    });

    render(
      <CreateWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />,
    );

    fireEvent.change(screen.getByLabelText("Name*"), {
      target: { value: "test-ws" },
    });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "desc" },
    });
    fireEvent.change(screen.getByLabelText("Default Artifact Root"), {
      target: { value: "s3://my-bucket" },
    });
    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(mockCreateWorkspace).toHaveBeenCalledWith({
        name: "test-ws",
        description: "desc",
        default_artifact_root: "s3://my-bucket",
      });
    });
  });

  it("shows error toast on creation failure", async () => {
    const mockCreateWorkspace = vi.spyOn(
      workspaceServiceModule,
      "createWorkspace",
    );
    mockCreateWorkspace.mockRejectedValue(new Error("409 Conflict"));

    render(
      <CreateWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />,
    );

    fireEvent.change(screen.getByLabelText("Name*"), {
      target: { value: "test-ws" },
    });
    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        "Failed to create workspace",
        "error",
      );
    });
  });

  it("calls onClose when Cancel is clicked", () => {
    render(
      <CreateWorkspaceModal
        isOpen={true}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
