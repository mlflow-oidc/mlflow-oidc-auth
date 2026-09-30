import { describe, it, expect } from "vitest";
import { formatDateTime } from "./format-date-time";

describe("formatDateTime", () => {
  it("renders a dash for missing or invalid values", () => {
    expect(formatDateTime(null)).toBe("-");
    expect(formatDateTime(undefined)).toBe("-");
    expect(formatDateTime("not a date")).toBe("-");
  });

  it("renders a valid timestamp in the local format", () => {
    const value = "2026-01-02T03:04:05+00:00";
    expect(formatDateTime(value)).toBe(new Date(value).toLocaleString());
  });
});
