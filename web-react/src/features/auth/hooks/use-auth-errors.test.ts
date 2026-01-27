import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useAuthErrors } from "./use-auth-errors";

describe("useAuthErrors", () => {
  beforeEach(() => {
    // Reset window.location.search
    vi.stubGlobal("location", {
      search: "",
    });
  });

  it("returns empty array when no error parameters", () => {
    vi.stubGlobal("location", { search: "" });
    const { result } = renderHook(() => useAuthErrors());
    expect(result.current).toEqual([]);
  });

  it("returns sanitized and decoded errors from URL params", () => {
    vi.stubGlobal("location", {
      search: "?error=First+Error&error=<b>Second</b>&error=  ",
    });
    const { result } = renderHook(() => useAuthErrors());
    expect(result.current).toEqual(["First Error", "Second"]);
  });

  it("filters out empty errors", () => {
    vi.stubGlobal("location", { search: "?error=&error=+++&error=Something" });
    const { result } = renderHook(() => useAuthErrors());
    expect(result.current).toEqual(["Something"]);
  });
});
