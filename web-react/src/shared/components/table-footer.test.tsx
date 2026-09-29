import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TableFooter, type TableFooterProps } from "./table-footer";

const renderFooter = (overrides: Partial<TableFooterProps> = {}) => {
  const props: TableFooterProps = {
    total: 134,
    page: 1,
    pageSize: 20,
    onPageChange: vi.fn(),
    onPageSizeChange: vi.fn(),
    ...overrides,
  };
  render(<TableFooter {...props} />);
  return props;
};

describe("TableFooter", () => {
  it.each([
    [{ total: 134, page: 1, pageSize: 20 }, "1–20 of 134"],
    [{ total: 134, page: 2, pageSize: 20 }, "21–40 of 134"],
    [{ total: 134, page: 7, pageSize: 20 }, "121–134 of 134"],
    [{ total: 134, page: 2, pageSize: 80 }, "81–134 of 134"],
    [{ total: 0, page: 1, pageSize: 20 }, "0 of 0"],
    [{ total: 134, page: 1, pageSize: "all" }, "All 134"],
    [{ total: 5, page: 1, pageSize: 20 }, "1–5 of 5"],
  ] as const)("shows the range for %j as %s", (props, label) => {
    renderFooter(props);
    expect(screen.getByTestId("pagination-range")).toHaveTextContent(label);
  });

  it("clamps an out-of-range page in the label", () => {
    renderFooter({ total: 30, page: 9, pageSize: 20 });
    expect(screen.getByTestId("pagination-range")).toHaveTextContent(
      "21–30 of 30",
    );
  });

  it("disables previous and first on the first page", () => {
    renderFooter({ page: 1 });
    expect(
      screen.getByRole("button", { name: "Previous page" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "First page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Last page" })).toBeEnabled();
  });

  it("disables next and last on the last page", () => {
    renderFooter({ page: 7 });
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Last page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeEnabled();
  });

  it("moves between pages", () => {
    const props = renderFooter({ page: 3 });
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(props.onPageChange).toHaveBeenLastCalledWith(4);
    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    expect(props.onPageChange).toHaveBeenLastCalledWith(2);
    fireEvent.click(screen.getByRole("button", { name: "First page" }));
    expect(props.onPageChange).toHaveBeenLastCalledWith(1);
    fireEvent.click(screen.getByRole("button", { name: "Last page" }));
    expect(props.onPageChange).toHaveBeenLastCalledWith(7);
  });

  it.each([
    ["40", 40],
    ["80", 80],
    ["All", "all"],
  ] as const)(
    "selecting %s changes the page size and goes back to page 1",
    async (option, size) => {
      const props = renderFooter({ page: 3 });
      await userEvent.selectOptions(
        screen.getByLabelText("Rows per page"),
        option,
      );
      expect(props.onPageSizeChange).toHaveBeenCalledWith(size);
      expect(props.onPageChange).toHaveBeenCalledWith(1);
    },
  );

  it("offers 20, 40, 80 and All and shows the current size", () => {
    renderFooter({ pageSize: 40 });
    const select = screen.getByLabelText<HTMLSelectElement>("Rows per page");
    expect(select.value).toBe("40");
    expect(
      Array.from(select.options).map((option) => option.textContent),
    ).toEqual(["20", "40", "80", "All"]);
  });

  it("hides prev/next when everything fits on one page but keeps the size select", () => {
    renderFooter({ total: 12, pageSize: 20 });
    expect(
      screen.queryByRole("button", { name: "Previous page" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Next page" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Rows per page")).toBeInTheDocument();
  });

  it("hides prev/next when All is selected", () => {
    renderFooter({ total: 500, pageSize: "all" });
    expect(
      screen.queryByRole("button", { name: "Next page" }),
    ).not.toBeInTheDocument();
  });

  it("is a labelled navigation landmark operable from the keyboard", async () => {
    const props = renderFooter({ page: 1 });
    expect(
      screen.getByRole("navigation", { name: "Pagination" }),
    ).toBeInTheDocument();

    const user = userEvent.setup();
    // Select, then the enabled Next button (First/Previous are disabled and skipped).
    await user.tab();
    expect(screen.getByLabelText("Rows per page")).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Next page" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(props.onPageChange).toHaveBeenCalledWith(2);
  });
});
