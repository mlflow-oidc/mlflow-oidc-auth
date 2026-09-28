import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { UserTokensPanel } from "./user-tokens-panel";
import * as hookModule from "../hooks/use-user-tokens";
import * as service from "../services/user-token-service";
import type { UserToken } from "../../../shared/types/user";

const mockShowToast = vi.fn();
const mockRefresh = vi.fn();

vi.mock("../hooks/use-user-tokens");
vi.mock("../services/user-token-service");
vi.mock("../../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

const tokens: UserToken[] = [
  {
    id: 1,
    name: "ci-pipeline",
    token_prefix: "ab12cd34",
    created_at: "2026-09-01T00:00:00Z",
    created_by: "alice",
    expires_at: "2027-01-01T23:59:59Z",
    last_used_at: "2026-09-20T10:00:00Z",
    active: true,
  },
  {
    id: 2,
    name: "old-laptop",
    token_prefix: null,
    created_at: "2025-01-01T00:00:00Z",
    created_by: null,
    expires_at: "2025-06-01T00:00:00Z",
    last_used_at: null,
    active: false,
  },
];

function mockTokens(
  overrides: Partial<ReturnType<typeof hookModule.useUserTokens>> = {},
) {
  vi.mocked(hookModule.useUserTokens).mockReturnValue({
    tokens,
    isLoading: false,
    error: null,
    refresh: mockRefresh,
    ...overrides,
  });
}

const rowOf = (name: string) =>
  screen.getByText(name).closest('[role="row"]') as HTMLElement;

describe("UserTokensPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTokens();
  });

  it("lists tokens with prefix, carried-over marker and status", () => {
    render(<UserTokensPanel />);
    expect(hookModule.useUserTokens).toHaveBeenCalledWith(undefined);

    const active = rowOf("ci-pipeline");
    expect(within(active).getByText("mlf_ab12cd34_…")).toBeInTheDocument();
    expect(within(active).getByText("Active")).toBeInTheDocument();

    const expired = rowOf("old-laptop");
    const carried = within(expired).getByText("Carried over");
    expect(carried).toHaveAttribute(
      "title",
      expect.stringContaining("before the upgrade to named tokens"),
    );
    expect(within(expired).getByText("Expired")).toBeInTheDocument();
    expect(within(expired).getByText("-")).toBeInTheDocument();
  });

  it("places Create token beside the search box and has no revoke-all for self", () => {
    render(<UserTokensPanel />);
    const create = screen.getByRole("button", { name: "Create token" });
    const search = screen.getByPlaceholderText("Search tokens...");
    expect(create.parentElement).toBe(search.closest("form")?.parentElement);
    expect(
      screen.queryByRole("button", { name: "Revoke all tokens" }),
    ).not.toBeInTheDocument();
  });

  it("filters by name on search", () => {
    render(<UserTokensPanel />);
    fireEvent.change(screen.getByPlaceholderText("Search tokens..."), {
      target: { value: "laptop" },
    });
    fireEvent.submit(
      screen.getByPlaceholderText("Search tokens...").closest("form")!,
    );
    expect(screen.queryByText("ci-pipeline")).not.toBeInTheDocument();
    expect(screen.getByText("old-laptop")).toBeInTheDocument();
  });

  it("shows loading and error states", () => {
    mockTokens({ tokens: [], isLoading: true });
    const { rerender } = render(<UserTokensPanel />);
    expect(screen.getByText("Loading tokens...")).toBeInTheDocument();

    mockTokens({ tokens: [], error: new Error("nope") });
    rerender(<UserTokensPanel />);
    expect(screen.getByText("Error: nope")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try Again" }));
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("deletes a token only after confirmation", async () => {
    vi.mocked(service.deleteUserToken).mockResolvedValue({ deleted: 1 });
    render(<UserTokensPanel />);

    fireEvent.click(screen.getByTitle("Delete token ci-pipeline"));
    expect(service.deleteUserToken).not.toHaveBeenCalled();
    expect(
      screen.getByText("Delete token", { selector: "h4" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete token" }));
    await waitFor(() =>
      expect(service.deleteUserToken).toHaveBeenCalledWith(undefined, 1),
    );
    expect(mockShowToast).toHaveBeenCalledWith(
      'Token "ci-pipeline" deleted',
      "success",
    );
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("reports a failed delete", async () => {
    vi.mocked(service.deleteUserToken).mockRejectedValue(
      new Error('HTTP 404: {"detail": "Token not found"}'),
    );
    render(<UserTokensPanel />);
    fireEvent.click(screen.getByTitle("Delete token ci-pipeline"));
    fireEvent.click(screen.getByRole("button", { name: "Delete token" }));
    await waitFor(() =>
      expect(mockShowToast).toHaveBeenCalledWith("Token not found", "error"),
    );
  });

  it("opens the create dialog and refreshes after a token is issued", async () => {
    vi.mocked(service.createUserToken).mockResolvedValue({
      ...tokens[0],
      id: 9,
      name: "new",
      token: "mlf_secret",
    });
    render(<UserTokensPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));
    fireEvent.change(screen.getByLabelText(/^Name/), {
      target: { value: "new" },
    });
    const dialog = screen.getByLabelText(/^Name/).closest("form")!;
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Create token" }),
    );

    expect(await screen.findByLabelText("Token")).toHaveValue("mlf_secret");
    expect(mockShowToast).toHaveBeenCalledWith(
      'Token "new" created',
      "success",
    );
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("keeps the plaintext on screen while the list refreshes after a create", async () => {
    const issued = {
      ...tokens[0],
      id: 9,
      name: "first",
      token: "mlf_ab12cd34_plaintext",
    };
    vi.mocked(service.createUserToken).mockResolvedValue(issued);
    mockTokens({ tokens: [tokens[1]] });
    const { rerender } = render(<UserTokensPanel />);

    // Start from an empty list (the table and search show, with no rows).
    mockTokens({ tokens: [] });
    rerender(<UserTokensPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Create token" }));
    fireEvent.change(screen.getByLabelText(/^Name/), {
      target: { value: "first" },
    });
    const form = screen.getByLabelText(/^Name/).closest("form")!;
    fireEvent.click(within(form).getByRole("button", { name: "Create token" }));
    expect(await screen.findByLabelText("Token")).toHaveValue(
      "mlf_ab12cd34_plaintext",
    );
    expect(mockRefresh).toHaveBeenCalled();

    // The refresh is in flight: the list gate shows "Loading", the dialog must survive it.
    mockTokens({ tokens: [], isLoading: true });
    rerender(<UserTokensPanel />);
    expect(screen.getByText("Loading tokens...")).toBeInTheDocument();
    expect(screen.getByLabelText("Token")).toHaveValue(
      "mlf_ab12cd34_plaintext",
    );

    // The server prunes expired tokens on issue, so the refreshed list holds only the new one.
    mockTokens({ tokens: [{ ...issued }] });
    rerender(<UserTokensPanel />);
    expect(screen.getByLabelText("Token")).toHaveValue(
      "mlf_ab12cd34_plaintext",
    );
    expect(screen.queryByText("old-laptop")).not.toBeInTheDocument();
  });

  describe("admin view of another account", () => {
    it("uses the account's tokens and revokes all after confirmation", async () => {
      vi.mocked(service.revokeAllUserTokens).mockResolvedValue({ revoked: 2 });
      render(<UserTokensPanel username="svc-bot" />);
      expect(hookModule.useUserTokens).toHaveBeenCalledWith("svc-bot");

      fireEvent.click(
        screen.getByRole("button", { name: "Revoke all tokens" }),
      );
      expect(service.revokeAllUserTokens).not.toHaveBeenCalled();
      expect(screen.getByText(/All 2 tokens of/)).toBeInTheDocument();

      const confirm = screen
        .getAllByRole("button", { name: "Revoke all tokens" })
        .at(-1)!;
      fireEvent.click(confirm);
      await waitFor(() =>
        expect(service.revokeAllUserTokens).toHaveBeenCalledWith("svc-bot"),
      );
      expect(mockShowToast).toHaveBeenCalledWith(
        "2 tokens of svc-bot revoked",
        "success",
      );
      expect(mockRefresh).toHaveBeenCalled();
    });

    it("reports a failed revoke-all", async () => {
      vi.mocked(service.revokeAllUserTokens).mockRejectedValue(new Error("x"));
      render(<UserTokensPanel username="svc-bot" />);
      fireEvent.click(
        screen.getByRole("button", { name: "Revoke all tokens" }),
      );
      fireEvent.click(
        screen.getAllByRole("button", { name: "Revoke all tokens" }).at(-1)!,
      );
      await waitFor(() =>
        expect(mockShowToast).toHaveBeenCalledWith(
          "Failed to revoke tokens",
          "error",
        ),
      );
    });

    it("deletes through the admin endpoint", async () => {
      vi.mocked(service.deleteUserToken).mockResolvedValue({ deleted: 1 });
      render(<UserTokensPanel username="svc-bot" />);
      fireEvent.click(screen.getByTitle("Delete token old-laptop"));
      fireEvent.click(screen.getByRole("button", { name: "Delete token" }));
      await waitFor(() =>
        expect(service.deleteUserToken).toHaveBeenCalledWith("svc-bot", 2),
      );
    });

    it("disables revoke-all when the account has no tokens", () => {
      mockTokens({ tokens: [] });
      render(<UserTokensPanel username="svc-bot" />);
      expect(
        screen.getByRole("button", { name: "Revoke all tokens" }),
      ).toBeDisabled();
    });
  });
});
