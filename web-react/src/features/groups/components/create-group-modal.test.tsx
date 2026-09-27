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

  it("creates the group and calls onCreated on success", async () => {
    vi.spyOn(entityService, "createGroup").mockResolvedValue({
      message: "Group data-team successfully created",
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

  it("shows an error toast and does not call onCreated when the request fails", async () => {
    vi.spyOn(entityService, "createGroup").mockRejectedValue(
      new Error("Group name must not contain '/', '?', '#' or '%'"),
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
