import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SearchInput } from "./search-input";

describe("SearchInput", () => {
  it("renders correctly", () => {
    render(
      <SearchInput
        value=""
        onInputChange={() => {}}
        onSubmit={() => {}}
        onClear={() => {}}
      />
    );
    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
  });

  it("calls onInputChange", () => {
    const handleChange = vi.fn();
    render(
      <SearchInput
        value=""
        onInputChange={handleChange}
        onSubmit={() => {}}
        onClear={() => {}}
      />
    );
    
    const input = screen.getByPlaceholderText("Search...");
    fireEvent.change(input, { target: { value: "test" } });
    expect(handleChange).toHaveBeenCalled();
  });

  it("calls onSubmit", () => {
    const handleSubmit = vi.fn((e) => e.preventDefault());
    render(
      <SearchInput
        value="test"
        onInputChange={() => {}}
        onSubmit={handleSubmit}
        onClear={() => {}}
      />
    );
    
    const submitBtn = screen.getByTitle("Search");
    fireEvent.click(submitBtn);
    
    expect(handleSubmit).toHaveBeenCalled();
  });

  it("shows clear button when value is present and calls onClear", () => {
    const handleClear = vi.fn();
    render(
      <SearchInput
        value="test"
        onInputChange={() => {}}
        onSubmit={() => {}}
        onClear={handleClear}
      />
    );
    
    const clearBtn = screen.getByTitle("Clear search");
    expect(clearBtn).toBeInTheDocument();
    
    fireEvent.click(clearBtn);
    expect(handleClear).toHaveBeenCalled();
  });

  it("hides clear button when empty", () => {
    render(
      <SearchInput
        value=""
        onInputChange={() => {}}
        onSubmit={() => {}}
        onClear={() => {}}
      />
    );
    
    expect(screen.queryByTitle("Clear search")).toBeNull();
  });
});
