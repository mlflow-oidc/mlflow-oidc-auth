import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { UserIdentitiesModal } from "./user-identities-modal";
import * as service from "../services/user-identity-service";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import type { ToastContextType } from "../../../shared/components/toast/toast-context-val";

vi.mock("../services/user-identity-service");
vi.mock("../../../shared/components/toast/use-toast");

const GITHUB = {
  provider_id: "ci",
  subject: "repo:org/app:ref:refs/heads/main",
};

describe("UserIdentitiesModal", () => {
  const showToast = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast,
      removeToast: vi.fn(),
    } as unknown as ToastContextType);
    vi.mocked(service.listUserIdentities).mockResolvedValue([GITHUB]);
    vi.mocked(service.unbindUserIdentity).mockResolvedValue({ deleted: 1 });
  });

  it("lists the identities bound to the user", async () => {
    render(<UserIdentitiesModal username="ci-bot" onClose={vi.fn()} />);

    expect(await screen.findByText(GITHUB.subject)).toBeInTheDocument();
    expect(screen.getByText("ci")).toBeInTheDocument();
  });

  it("unbinds one only after confirmation, and reloads", async () => {
    render(<UserIdentitiesModal username="ci-bot" onClose={vi.fn()} />);
    fireEvent.click(
      await screen.findByRole("button", {
        name: `Unbind ci identity ${GITHUB.subject}`,
      }),
    );
    expect(service.unbindUserIdentity).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Confirm unbind" }));

    await waitFor(() =>
      expect(service.unbindUserIdentity).toHaveBeenCalledWith("ci-bot", GITHUB),
    );
    await waitFor(() =>
      expect(service.listUserIdentities).toHaveBeenCalledTimes(2),
    );
    expect(showToast).toHaveBeenCalledWith(
      expect.stringContaining("unbound from ci-bot"),
      "success",
    );
  });

  it("says when nothing is bound, and renders nothing without a user", async () => {
    vi.mocked(service.listUserIdentities).mockResolvedValue([]);
    const { unmount } = render(
      <UserIdentitiesModal username="ci-bot" onClose={vi.fn()} />,
    );
    expect(await screen.findByText("No identities bound.")).toBeInTheDocument();
    unmount();

    const { container } = render(
      <UserIdentitiesModal username={null} onClose={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
