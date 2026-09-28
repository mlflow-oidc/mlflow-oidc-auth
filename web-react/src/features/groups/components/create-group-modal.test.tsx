import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CreateGroupModal } from "./create-group-modal";
import * as entityService from "../../../core/services/entity-service";
import * as useToastModule from "../../../shared/components/toast/use-toast";

vi.mock("../../../core/services/entity-service");
vi.mock("../../../shared/components/toast/use-toast");

describe("CreateGroupModal", () => {
  const showToast = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast,
      removeToast: vi.fn(),
    } as unknown as ReturnType<typeof useToastModule.useToast>);
  });

  it("disables Create until a name is entered", () => {
    render(
      <CreateGroupModal isOpen={true} onClose={vi.fn()} onCreated={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Group name\*/i), {
      target: { value: "data-team" },
    });

    expect(screen.getByRole("button", { name: "Create" })).not.toBeDisabled();
  });

  it("shows 'created' and calls onCreated when the backend returns 201", async () => {
    vi.spyOn(entityService, "createGroup").mockResolvedValue({
      message: "Group data-team successfully created",
      status: 201,
    });
    const onCreated = vi.fn();

    render(
      <CreateGroupModal
        isOpen={true}
        onClose={vi.fn()}
        onCreated={onCreated}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Group name\*/i), {
      target: { value: "  data-team  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(entityService.createGroup).toHaveBeenCalledWith("data-team");
    });
    expect(onCreated).toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith(
      'Group "data-team" created',
      "success",
    );
  });

  it("shows 'already exists' (not 'created') when the backend returns 200", async () => {
    vi.spyOn(entityService, "createGroup").mockResolvedValue({
      message: "Group data-team already exists",
      status: 200,
    });
    const onCreated = vi.fn();

    render(
      <CreateGroupModal
        isOpen={true}
        onClose={vi.fn()}
        onCreated={onCreated}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Group name\*/i), {
      target: { value: "data-team" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalled();
    });
    expect(showToast).toHaveBeenCalledWith(
      'Group "data-team" already exists',
      "success",
    );
    expect(showToast).not.toHaveBeenCalledWith(
      expect.stringContaining("created"),
      expect.anything(),
    );
  });

  it("shows the backend's error message and does not call onCreated on a 400", async () => {
    vi.spyOn(entityService, "createGroup").mockRejectedValue(
      new Error(
        `HTTP 400: ${JSON.stringify({ detail: "Group name must not contain '/', '?', '#' or '%'" })}`,
      ),
    );
    const onCreated = vi.fn();

    render(
      <CreateGroupModal
        isOpen={true}
        onClose={vi.fn()}
        onCreated={onCreated}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Group name\*/i), {
      target: { value: "bad/name" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(entityService.createGroup).toHaveBeenCalledWith("bad/name");
    });
    expect(onCreated).not.toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith(
      "Group name must not contain '/', '?', '#' or '%'",
      "error",
    );
  });

  it("falls back to a generic error message when the failure carries no detail", async () => {
    vi.spyOn(entityService, "createGroup").mockRejectedValue(
      new Error("Network error"),
    );
    const onCreated = vi.fn();

    render(
      <CreateGroupModal
        isOpen={true}
        onClose={vi.fn()}
        onCreated={onCreated}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Group name\*/i), {
      target: { value: "data-team" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(entityService.createGroup).toHaveBeenCalledWith("data-team");
    });
    expect(onCreated).not.toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith("Failed to create group", "error");
  });

  it("does not submit a blank (whitespace-only) name", () => {
    render(
      <CreateGroupModal isOpen={true} onClose={vi.fn()} onCreated={vi.fn()} />,
    );

    fireEvent.change(screen.getByLabelText(/Group name\*/i), {
      target: { value: "   " },
    });

    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
  });
});
