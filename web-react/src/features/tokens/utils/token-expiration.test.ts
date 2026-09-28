import { describe, it, expect } from "vitest";
import {
  endOfUtcDayIso,
  isWithinTokenDateBounds,
  tokenDateBounds,
  utcDateAfter,
} from "./token-expiration";

describe("token-expiration", () => {
  it("builds the end of the UTC day from the date parts", () => {
    expect(endOfUtcDayIso("2027-01-31")).toBe("2027-01-31T23:59:59Z");
    expect(endOfUtcDayIso("2028-02-29")).toBe("2028-02-29T23:59:59Z");
  });

  it("rejects malformed or impossible dates", () => {
    expect(endOfUtcDayIso("")).toBeNull();
    expect(endOfUtcDayIso("2027-1-5")).toBeNull();
    expect(endOfUtcDayIso("2027-02-30")).toBeNull();
    expect(endOfUtcDayIso("2027-13-01")).toBeNull();
  });

  it("counts calendar days in UTC, not the viewer's timezone", () => {
    // 23:30 UTC on Dec 31: local "today" may already be Jan 1 east of UTC.
    const now = new Date(Date.UTC(2026, 11, 31, 23, 30));
    expect(utcDateAfter(now, 1)).toBe("2027-01-01");
    expect(utcDateAfter(now, 365)).toBe("2027-12-31");
  });

  it("bounds the picker to tomorrow ... today + 365 days", () => {
    const now = new Date(Date.UTC(2026, 8, 28, 12));
    const bounds = tokenDateBounds(now);
    expect(bounds).toEqual({
      min: "2026-09-29",
      max: "2027-09-28",
      defaultValue: "2026-12-27",
    });
    expect(isWithinTokenDateBounds("2026-09-28", bounds)).toBe(false);
    expect(isWithinTokenDateBounds("2026-09-29", bounds)).toBe(true);
    expect(isWithinTokenDateBounds("2027-09-28", bounds)).toBe(true);
    expect(isWithinTokenDateBounds("2027-09-29", bounds)).toBe(false);
  });

  it("keeps the latest allowed expiry within the backend's 366-day cap", () => {
    const now = new Date(Date.UTC(2026, 8, 28, 0, 0, 1));
    const latest = endOfUtcDayIso(tokenDateBounds(now).max);
    expect(latest).not.toBeNull();
    const lifetimeMs = new Date(latest as string).getTime() - now.getTime();
    expect(lifetimeMs).toBeLessThanOrEqual(366 * 24 * 60 * 60 * 1000);
  });
});
