import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { CreateScimTokenModal } from "./create-scim-token-modal";
import * as scimTokenService from "../services/scim-token-service";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import type { ScimTokenWithSecret } from "../../../shared/types/scim";

vi.mock("../services/scim-token-service");
vi.mock("../../../shared/components/toast/use-toast");

// No @types/node in this project; Node provides `process` at runtime regardless. This tells
// TypeScript just enough to compile the TZ override below, which is how this test simulates a
// viewer west of UTC (see `endOfLocalDayIso`'s doc comment in create-scim-token-modal.tsx).
declare const process: { env: Record<string, string | undefined> };

describe("CreateScimTokenModal", () => {
  const originalTz = process.env.TZ;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: vi.fn(),
      removeToast: vi.fn(),
    } as unknown as ReturnType<typeof useToastModule.useToast>);
  });

  afterEach(() => {
    vi.useRealTimers();
    process.env.TZ = originalTz;
  });

  // Honolulu is UTC-10 year-round (no DST), so "today" there is still "yesterday" in UTC for
  // most of the day — exactly the west-of-UTC case the fix targets.
  const HONOLULU = "Pacific/Honolulu";

  it("sets the date input's min to today in the viewer's local timezone, not UTC", () => {
    process.env.TZ = HONOLULU;
    // 2026-03-02T05:00:00Z is 2026-03-01 19:00 in Honolulu (UTC-10): same UTC day as local day
    // here, so instead pick a time where UTC has already rolled to the next day locally it has
    // not: 2026-03-02T09:30:00Z -> Honolulu local is still 2026-03-01 23:30.
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-02T09:30:00Z"));

    render(
      <CreateScimTokenModal isOpen={true} onClose={vi.fn()} onCreated={vi.fn()} />,
    );

    const dateInput = screen.getByLabelText(/Expires on/i);
    // Local date is still 2026-03-01, even though it's already 2026-03-02 in UTC.
    expect(dateInput).toHaveAttribute("min", "2026-03-01");
  });

  it("sends an expiry at the end of the picked day in local time, not UTC midnight", async () => {
    process.env.TZ = HONOLULU;

    const created: ScimTokenWithSecret = {
      id: 1,
      name: "New Token",
      token_prefix: "scim_abcd",
      created_at: "2026-03-01T23:30:00Z",
      created_by: "admin",
      last_used_at: null,
      expires_at: null,
      revoked_at: null,
      token: "scim_plaintext",
    };
    vi.spyOn(scimTokenService, "createScimToken").mockResolvedValue(created);

    render(
      <CreateScimTokenModal isOpen={true} onClose={vi.fn()} onCreated={vi.fn()} />,
    );

    fireEvent.change(screen.getByLabelText(/Name\*/i), {
      target: { value: "New Token" },
    });
    // Picking "today" (the local date shown as the input's min).
    fireEvent.change(screen.getByLabelText(/Expires on/i), {
      target: { value: "2026-03-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(scimTokenService.createScimToken).toHaveBeenCalled();
    });

    const call = vi.mocked(scimTokenService.createScimToken).mock.calls[0][0];
    // End of 2026-03-01 in Honolulu (UTC-10) is 2026-03-02T09:59:59.999Z. The old
    // `new Date("2026-03-01").toISOString()` behavior would have produced
    // 2026-03-01T00:00:00.000Z instead — UTC midnight of the picked date, nearly a full day
    // earlier, and already expired for most of the day it was picked on.
    expect(call.expires_at).toBe("2026-03-02T09:59:59.999Z");
  });

  it("omits expires_at when no date is picked", async () => {
    const created: ScimTokenWithSecret = {
      id: 1,
      name: "New Token",
      token_prefix: "scim_abcd",
      created_at: "2026-03-01T00:00:00Z",
      created_by: "admin",
      last_used_at: null,
      expires_at: null,
      revoked_at: null,
      token: "scim_plaintext",
    };
    vi.spyOn(scimTokenService, "createScimToken").mockResolvedValue(created);

    render(
      <CreateScimTokenModal isOpen={true} onClose={vi.fn()} onCreated={vi.fn()} />,
    );

    fireEvent.change(screen.getByLabelText(/Name\*/i), {
      target: { value: "New Token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(scimTokenService.createScimToken).toHaveBeenCalledWith(
        expect.objectContaining({ name: "New Token", expires_at: undefined }),
      );
    });
  });
});
