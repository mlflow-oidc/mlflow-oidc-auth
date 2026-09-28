import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { CreateUserTokenModal } from "./create-user-token-modal";
import * as service from "../services/user-token-service";
import type { UserTokenWithSecret } from "../../../shared/types/user";

vi.mock("../services/user-token-service");

const created: UserTokenWithSecret = {
  id: 5,
  name: "ci",
  token_prefix: "ab12cd34",
  created_at: "2026-09-28T12:00:00Z",
  created_by: "alice",
  expires_at: "2026-10-31T23:59:59Z",
  last_used_at: null,
  active: true,
  token: "mlf_ab12cd34_secret_value",
};

const writeText = vi.fn<(text: string) => Promise<void>>();

function renderModal(owner?: string) {
  const onClose = vi.fn();
  const onCreated = vi.fn();
  render(
    <CreateUserTokenModal
      isOpen
      onClose={onClose}
      onCreated={onCreated}
      owner={owner}
    />,
  );
  return { onClose, onCreated };
}

function fillForm(name: string, date: string) {
  fireEvent.change(screen.getByLabelText(/^Name/), {
    target: { value: name },
  });
  fireEvent.change(screen.getByLabelText(/^Expires on/), {
    target: { value: date },
  });
}

describe("CreateUserTokenModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(Date.UTC(2026, 8, 28, 12)));
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("limits the date picker to tomorrow ... one year and preselects a date", () => {
    renderModal();
    const date = screen.getByLabelText(/^Expires on/);
    expect(date).toHaveAttribute("min", "2026-09-29");
    expect(date).toHaveAttribute("max", "2027-09-28");
    expect(date).toHaveValue("2026-12-27");
    expect(screen.getByRole("button", { name: "Create token" })).toBeDisabled();
  });

  it("sends the end of the chosen UTC day and shows the secret once, with Done", async () => {
    vi.mocked(service.createUserToken).mockResolvedValue(created);
    const { onCreated, onClose } = renderModal();

    fillForm("  ci  ", "2026-10-31");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));

    await waitFor(() =>
      expect(service.createUserToken).toHaveBeenCalledWith(undefined, {
        name: "ci",
        expiration: "2026-10-31T23:59:59Z",
      }),
    );
    expect(onCreated).toHaveBeenCalledWith(created);
    expect(await screen.findByLabelText("Token")).toHaveValue(
      "mlf_ab12cd34_secret_value",
    );
    expect(screen.getByText(/will not be shown again/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Name/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Create token" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(onClose).toHaveBeenCalled();
    // The secret is gone once the dialog is dismissed.
    expect(screen.queryByLabelText("Token")).not.toBeInTheDocument();
  });

  it("issues for another account when an owner is given", async () => {
    vi.mocked(service.createUserToken).mockResolvedValue(created);
    renderModal("svc-bot");
    expect(screen.getByText("Create token for svc-bot")).toBeInTheDocument();
    fillForm("deploy", "2027-09-28");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));
    await waitFor(() =>
      expect(service.createUserToken).toHaveBeenCalledWith("svc-bot", {
        name: "deploy",
        expiration: "2027-09-28T23:59:59Z",
      }),
    );
  });

  it("surfaces a 409 from the server inside the dialog", async () => {
    vi.mocked(service.createUserToken).mockRejectedValue(
      new Error('HTTP 409: {"detail": "A token named \'ci\' already exists"}'),
    );
    const { onCreated } = renderModal();
    fillForm("ci", "2026-10-31");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A token named 'ci' already exists",
    );
    expect(onCreated).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/^Name/)).toHaveValue("ci");
  });

  it("rejects a date outside the allowed range", () => {
    renderModal();
    fillForm("ci", "2027-09-29");
    expect(screen.getByText(/Pick a date between/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create token" })).toBeDisabled();
  });

  it("confirms a successful copy", async () => {
    writeText.mockResolvedValue();
    vi.mocked(service.createUserToken).mockResolvedValue(created);
    renderModal();
    fillForm("ci", "2026-10-31");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));

    fireEvent.click(await screen.findByRole("button", { name: "Copy token" }));
    expect(await screen.findByText("Copied to clipboard.")).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith("mlf_ab12cd34_secret_value");
  });

  it("shows visible feedback when the copy fails", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    vi.mocked(service.createUserToken).mockResolvedValue(created);
    renderModal();
    fillForm("ci", "2026-10-31");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));

    fireEvent.click(await screen.findByRole("button", { name: "Copy token" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      /Could not copy to the clipboard/,
    );
  });

  it("reports a failed copy when the clipboard API is unavailable", async () => {
    Object.defineProperty(navigator, "clipboard", {
      value: undefined,
      configurable: true,
    });
    vi.mocked(service.createUserToken).mockResolvedValue(created);
    renderModal();
    fillForm("ci", "2026-10-31");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));

    fireEvent.click(await screen.findByRole("button", { name: "Copy token" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      /Could not copy to the clipboard/,
    );
  });

  it("cancel closes without calling the server", () => {
    const { onClose } = renderModal();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
    expect(service.createUserToken).not.toHaveBeenCalled();
  });

  it("never shows a secret that arrives after the dialog was closed", async () => {
    let resolve: (t: UserTokenWithSecret) => void = () => {};
    vi.mocked(service.createUserToken).mockReturnValue(
      new Promise<UserTokenWithSecret>((r) => {
        resolve = r;
      }),
    );
    const onCreated = vi.fn();
    const onClose = vi.fn();
    const props = { onClose, onCreated, owner: undefined };
    const { rerender } = render(<CreateUserTokenModal isOpen {...props} />);

    fillForm("ci", "2026-10-31");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));
    expect(screen.getByRole("button", { name: "Creating..." })).toBeDisabled();

    // Escape / the X button while the request is in flight.
    fireEvent.click(screen.getByRole("button", { name: "Close modal" }));
    expect(onClose).toHaveBeenCalled();
    rerender(<CreateUserTokenModal isOpen={false} {...props} />);

    await act(async () => {
      resolve(created);
      await Promise.resolve();
    });
    // The list is still told a token now exists...
    expect(onCreated).toHaveBeenCalledWith(created);

    // ...but the next opening starts on a fresh form, not the old secret.
    rerender(<CreateUserTokenModal isOpen {...props} />);
    expect(screen.queryByLabelText("Token")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/^Name/)).toHaveValue("");
    expect(screen.getByRole("button", { name: "Create token" })).toBeDisabled();
  });

  it("reopens on a fresh form after a token was shown", async () => {
    vi.mocked(service.createUserToken).mockResolvedValue(created);
    const props = { onClose: vi.fn(), onCreated: vi.fn(), owner: undefined };
    const { rerender } = render(<CreateUserTokenModal isOpen {...props} />);
    fillForm("ci", "2026-10-31");
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));
    await screen.findByLabelText("Token");

    rerender(<CreateUserTokenModal isOpen={false} {...props} />);
    rerender(<CreateUserTokenModal isOpen {...props} />);
    expect(screen.queryByLabelText("Token")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/^Name/)).toHaveValue("");
    expect(screen.getByLabelText(/^Expires on/)).toHaveValue("2026-12-27");
  });

  it("recomputes the date bounds each time it opens", () => {
    vi.setSystemTime(new Date(Date.UTC(2026, 8, 28, 23, 59)));
    const props = { onClose: vi.fn(), onCreated: vi.fn(), owner: undefined };
    const { rerender } = render(
      <CreateUserTokenModal isOpen={false} {...props} />,
    );
    rerender(<CreateUserTokenModal isOpen {...props} />);
    let date = screen.getByLabelText(/^Expires on/);
    expect(date).toHaveAttribute("min", "2026-09-29");
    expect(date).toHaveAttribute("max", "2027-09-28");

    rerender(<CreateUserTokenModal isOpen={false} {...props} />);
    // Past UTC midnight: yesterday's bounds would now be stale.
    vi.setSystemTime(new Date(Date.UTC(2026, 8, 29, 0, 1)));
    rerender(<CreateUserTokenModal isOpen {...props} />);
    date = screen.getByLabelText(/^Expires on/);
    expect(date).toHaveAttribute("min", "2026-09-30");
    expect(date).toHaveAttribute("max", "2027-09-29");
    expect(date).toHaveValue("2026-12-28");
  });
});
