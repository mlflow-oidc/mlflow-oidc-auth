import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSearch } from "./use-search";
import React from "react";

describe("useSearch", () => {
    it("initializes with empty terms", () => {
        const { result } = renderHook(() => useSearch());
        expect(result.current.searchTerm).toBe("");
        expect(result.current.submittedTerm).toBe("");
    });

    it("updates searchTerm on input change", () => {
        const { result } = renderHook(() => useSearch());
        act(() => {
            result.current.handleInputChange({ target: { value: "test" } } as React.ChangeEvent<HTMLInputElement>);
        });
        expect(result.current.searchTerm).toBe("test");
    });

    it("updates submittedTerm on form submit", () => {
        const { result } = renderHook(() => useSearch());
        act(() => {
            result.current.handleInputChange({ target: { value: "search query" } } as React.ChangeEvent<HTMLInputElement>);
        });
        act(() => {
            result.current.handleSearchSubmit({ preventDefault: () => {} } as React.FormEvent<HTMLFormElement>);
        });
        expect(result.current.submittedTerm).toBe("search query");
    });

    it("clears both terms on clear", () => {
        const { result } = renderHook(() => useSearch());
        act(() => {
            result.current.handleInputChange({ target: { value: "test" } } as React.ChangeEvent<HTMLInputElement>);
            result.current.handleSearchSubmit({ preventDefault: () => {} } as React.FormEvent<HTMLFormElement>);
        });
        act(() => {
            result.current.handleClearSearch();
        });
        expect(result.current.searchTerm).toBe("");
        expect(result.current.submittedTerm).toBe("");
    });
});
