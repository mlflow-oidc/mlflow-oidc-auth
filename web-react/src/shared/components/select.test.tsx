import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Select } from "./select";

describe("Select", () => {
  it("renders with options (string array)", () => {
    render(
      <Select
        id="test-select"
        label="Choose One"
        options={["Option A", "Option B"]}
      />,
    );

    expect(screen.getByLabelText("Choose One")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Option A" })).toHaveValue(
      "Option A",
    );
    expect(screen.getByRole("option", { name: "Option B" })).toHaveValue(
      "Option B",
    );
  });

  it("renders with options (object array)", () => {
    const options = [
      { label: "Label 1", value: "val1" },
      { label: "Label 2", value: "val2" },
    ];
    render(<Select id="test-select" label="Choose One" options={options} />);

    expect(screen.getByRole("option", { name: "Label 1" })).toHaveValue("val1");
    expect(screen.getByRole("option", { name: "Label 2" })).toHaveValue("val2");
  });

  it("renders error message", () => {
    render(
      <Select id="test-select" options={[]} error="Something went wrong" />,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveClass("border-red-500");
  });

  it("forwards props", () => {
    const handleChange = vi.fn();
    render(
      <Select
        id="test-select"
        options={["A"]}
        onChange={handleChange}
        disabled
      />,
    );

    const select = screen.getByRole("combobox");
    expect(select).toBeDisabled();
  });
});
