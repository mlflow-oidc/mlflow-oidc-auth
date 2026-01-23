import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { WebhookForm } from "./webhook-form";

describe("WebhookForm", () => {
  const mockOnSubmit = vi.fn();
  const mockOnCancel = vi.fn();

  it("renders correctly with default values", () => {
    render(
      <WebhookForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        submitLabel="Submit"
        isSubmitting={false}
      />
    );

    expect(screen.getByLabelText("Name*")).toHaveValue("");
    expect(screen.getByLabelText("URL*")).toHaveValue("");
    expect(screen.getByLabelText("Secret (Optional)")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Submit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("renders correctly with initial data", () => {
    const initialData = {
      name: "Initial Name",
      url: "https://initial-url.com",
      events: ["prompt.created"],
      secret: "initial-secret",
    };

    render(
      <WebhookForm
        initialData={initialData}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        submitLabel="Update"
        isSubmitting={false}
        isEdit
      />
    );

    expect(screen.getByLabelText("Name*")).toHaveValue("Initial Name");
    expect(screen.getByLabelText("URL*")).toHaveValue("https://initial-url.com");
    expect(screen.getByLabelText("Secret (Optional)")).toHaveValue("initial-secret");
    expect(screen.getByLabelText("prompt.created")).toBeChecked();
  });

  it("shows validation errors on empty submission", async () => {
    render(
      <WebhookForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        submitLabel="Submit"
        isSubmitting={false}
      />
    );

    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(screen.getByText("Name is required")).toBeInTheDocument();
      expect(screen.getByText("URL is required")).toBeInTheDocument();
      expect(screen.getByText("At least one event must be selected")).toBeInTheDocument();
    });
    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it("validates URL format", async () => {
    render(
      <WebhookForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        submitLabel="Submit"
        isSubmitting={false}
      />
    );

    fireEvent.change(screen.getByLabelText("URL*"), { target: { value: "not-a-url" } });
    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(screen.getByText("Invalid URL format")).toBeInTheDocument();
    });
  });

  it("calls onSubmit with form data when valid", async () => {
    render(
      <WebhookForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        submitLabel="Submit"
        isSubmitting={false}
      />
    );

    fireEvent.change(screen.getByLabelText("Name*"), { target: { value: "Test Webhook" } });
    fireEvent.change(screen.getByLabelText("URL*"), { target: { value: "https://example.com" } });
    fireEvent.click(screen.getByLabelText("registered_model.created"));

    fireEvent.submit(screen.getByRole("form"));

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        name: "Test Webhook",
        url: "https://example.com",
        events: ["registered_model.created"],
        secret: "",
      });
    });
  });

  it("handles event toggling", () => {
    render(
      <WebhookForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        submitLabel="Submit"
        isSubmitting={false}
      />
    );

    const checkbox = screen.getByLabelText("registered_model.created");
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });

  it("calls onCancel when cancel button is clicked", () => {
    render(
      <WebhookForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        submitLabel="Submit"
        isSubmitting={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockOnCancel).toHaveBeenCalled();
  });

  it("disables buttons when isSubmitting is true", () => {
    render(
      <WebhookForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        submitLabel="Submit"
        isSubmitting={true}
      />
    );

    expect(screen.getByRole("button", { name: "Creating..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("shows 'Updating...' when isSubmitting and isEdit are true", () => {
    render(
      <WebhookForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        submitLabel="Update"
        isSubmitting={true}
        isEdit
      />
    );

    expect(screen.getByRole("button", { name: "Updating..." })).toBeInTheDocument();
  });
});
