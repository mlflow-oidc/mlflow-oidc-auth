import { render, screen, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { _resetPageSizeForTests } from "../../core/hooks/use-page-size";
import { installLocalStorageMock } from "../../tests/local-storage-mock";

installLocalStorageMock();
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { EntityListTable } from "./entity-list-table";
import type { ColumnConfig } from "../types/table";

describe("EntityListTable", () => {
  beforeEach(() => {
    window.localStorage.clear();
    _resetPageSizeForTests();
  });

  interface MockItem extends Record<string, unknown> {
    id: string;
    name: string;
  }

  const mockColumns: ColumnConfig<MockItem>[] = [
    { header: "Name", render: (item) => item.name },
    { header: "ID", render: (item) => item.id },
  ];

  const mockData: MockItem[] = [
    { id: "1", name: "Item 1" },
    { id: "2", name: "Item 2" },
  ];

  it("renders object table with data", () => {
    render(
      <EntityListTable data={mockData} columns={mockColumns} searchTerm="" />,
    );

    expect(screen.getByText("Item 1")).toBeInTheDocument();
    expect(screen.getByText("Item 2")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("ID")).toBeInTheDocument();
  });

  it("renders empty state when no data", () => {
    render(<EntityListTable data={[]} columns={mockColumns} searchTerm="" />);

    expect(screen.getByText("No items found")).toBeInTheDocument();
  });

  it("renders empty state with search term", () => {
    render(
      <EntityListTable
        data={[]}
        columns={mockColumns}
        searchTerm="found nothing"
      />,
    );

    expect(
      screen.getByText('No items found for "found nothing"'),
    ).toBeInTheDocument();
  });

  describe("with getRowHref", () => {
    function LocationDisplay() {
      const location = useLocation();
      return <div data-testid="location">{location.pathname}</div>;
    }

    const onAction = vi.fn<(id: string) => void>();
    const interactiveColumns: ColumnConfig<MockItem>[] = [
      { header: "Name", render: (item) => item.name },
      {
        header: "Actions",
        render: (item) => (
          <button
            type="button"
            onClick={() => {
              onAction(item.id);
            }}
          >
            Act {item.id}
          </button>
        ),
      },
    ];

    const renderNavigable = (getRowHref?: (item: MockItem) => string) =>
      render(
        <MemoryRouter initialEntries={["/list"]}>
          <Routes>
            <Route
              path="*"
              element={
                <>
                  <EntityListTable
                    data={mockData}
                    columns={interactiveColumns}
                    searchTerm=""
                    getRowHref={getRowHref}
                  />
                  <LocationDisplay />
                </>
              }
            />
          </Routes>
        </MemoryRouter>,
      );

    it("navigates to the row href when the row is clicked", () => {
      renderNavigable((item) => `/items/${item.id}`);

      fireEvent.click(screen.getByText("Item 2"));
      expect(screen.getByTestId("location")).toHaveTextContent("/items/2");
    });

    it("gives rows a pointer cursor and an aria-hidden chevron", () => {
      renderNavigable((item) => `/items/${item.id}`);

      const rows = screen.getAllByRole("row").slice(1);
      expect(rows).toHaveLength(2);
      rows.forEach((row) => expect(row).toHaveClass("cursor-pointer"));
      const chevrons = screen.getAllByTestId("row-chevron");
      expect(chevrons).toHaveLength(2);
      chevrons.forEach((chevron) =>
        expect(chevron).toHaveAttribute("aria-hidden", "true"),
      );
    });

    it("does not navigate when a button inside the row is clicked", () => {
      onAction.mockClear();
      renderNavigable((item) => `/items/${item.id}`);

      fireEvent.click(screen.getByRole("button", { name: "Act 1" }));
      expect(onAction).toHaveBeenCalledWith("1");
      expect(screen.getByTestId("location")).toHaveTextContent("/list");
    });

    it("has no pointer cursor, chevron or navigation without getRowHref", () => {
      renderNavigable();

      const rows = screen.getAllByRole("row").slice(1);
      rows.forEach((row) => expect(row).not.toHaveClass("cursor-pointer"));
      expect(screen.queryByTestId("row-chevron")).not.toBeInTheDocument();

      fireEvent.click(screen.getByText("Item 1"));
      expect(screen.getByTestId("location")).toHaveTextContent("/list");
    });
  });

  describe("pagination", () => {
    const many = (count: number, prefix = "Row"): MockItem[] =>
      Array.from({ length: count }, (_, i) => ({
        id: `${prefix}-${i + 1}`,
        name: `${prefix} ${i + 1}`,
      }));
    const nameColumns: ColumnConfig<MockItem>[] = [
      { header: "Name", render: (item) => item.name },
    ];
    const bodyRowCount = () => screen.getAllByRole("row").length - 1;
    const range = () => screen.getByTestId("pagination-range");

    describe("client mode", () => {
      it("shows the first page of 20 by default", () => {
        render(
          <EntityListTable data={many(45)} columns={nameColumns} searchTerm="" />,
        );
        expect(bodyRowCount()).toBe(20);
        expect(screen.getByText("Row 1")).toBeInTheDocument();
        expect(screen.queryByText("Row 21")).not.toBeInTheDocument();
        expect(range()).toHaveTextContent("1–20 of 45");
      });

      it("slices the next page", () => {
        render(
          <EntityListTable data={many(45)} columns={nameColumns} searchTerm="" />,
        );
        fireEvent.click(screen.getByRole("button", { name: "Next page" }));
        expect(screen.getByText("Row 21")).toBeInTheDocument();
        expect(screen.queryByText("Row 1")).not.toBeInTheDocument();
        expect(range()).toHaveTextContent("21–40 of 45");

        fireEvent.click(screen.getByRole("button", { name: "Last page" }));
        expect(bodyRowCount()).toBe(5);
        expect(range()).toHaveTextContent("41–45 of 45");
      });

      it("goes back to page 1 when the search changes", () => {
        const { rerender } = render(
          <EntityListTable data={many(45)} columns={nameColumns} searchTerm="" />,
        );
        fireEvent.click(screen.getByRole("button", { name: "Next page" }));
        expect(range()).toHaveTextContent("21–40 of 45");

        rerender(
          <EntityListTable
            data={many(30)}
            columns={nameColumns}
            searchTerm="Row"
          />,
        );
        expect(range()).toHaveTextContent("1–20 of 30");
        expect(screen.getByText("Row 1")).toBeInTheDocument();
      });

      it("clamps the page when the data shrinks", () => {
        const { rerender } = render(
          <EntityListTable data={many(45)} columns={nameColumns} searchTerm="" />,
        );
        fireEvent.click(screen.getByRole("button", { name: "Last page" }));
        expect(range()).toHaveTextContent("41–45 of 45");

        rerender(
          <EntityListTable data={many(25)} columns={nameColumns} searchTerm="" />,
        );
        expect(range()).toHaveTextContent("21–25 of 25");
        expect(screen.getByText("Row 21")).toBeInTheDocument();
      });

      it("changes the page size, resets to page 1 and shares it with other tables", async () => {
        render(
          <>
            <EntityListTable
              data={many(100, "A")}
              columns={nameColumns}
              searchTerm=""
            />
            <EntityListTable
              data={many(100, "B")}
              columns={nameColumns}
              searchTerm=""
            />
          </>,
        );
        const [firstNext] = screen.getAllByRole("button", {
          name: "Next page",
        });
        fireEvent.click(firstNext);
        const [firstSelect] = screen.getAllByLabelText("Rows per page");
        await userEvent.selectOptions(firstSelect, "40");

        const ranges = screen.getAllByTestId("pagination-range");
        expect(ranges[0]).toHaveTextContent("1–40 of 100");
        expect(ranges[1]).toHaveTextContent("1–40 of 100");
        expect(window.localStorage.getItem("mlflow-oidc-auth:page-size")).toBe(
          "40",
        );
      });

      it("renders every row with All", async () => {
        render(
          <EntityListTable data={many(45)} columns={nameColumns} searchTerm="" />,
        );
        await userEvent.selectOptions(
          screen.getByLabelText("Rows per page"),
          "All",
        );
        expect(bodyRowCount()).toBe(45);
        expect(range()).toHaveTextContent("All 45");
        expect(
          screen.queryByRole("button", { name: "Next page" }),
        ).not.toBeInTheDocument();
      });

      it("shows 0 of 0 and the empty state for no data", () => {
        render(<EntityListTable data={[]} columns={nameColumns} searchTerm="" />);
        expect(range()).toHaveTextContent("0 of 0");
        expect(screen.getByText("No items found")).toBeInTheDocument();
      });
    });

    describe("server mode", () => {
      it("renders data as-is and labels the range from total", () => {
        const onPageChange = vi.fn();
        render(
          <EntityListTable
            data={many(20)}
            columns={nameColumns}
            searchTerm=""
            pagination={{ total: 134, page: 3, pageSize: 20, onPageChange }}
          />,
        );
        // 20 rows rendered even though page 3 would slice them away locally.
        expect(bodyRowCount()).toBe(20);
        expect(screen.getByText("Row 1")).toBeInTheDocument();
        expect(range()).toHaveTextContent("41–60 of 134");

        fireEvent.click(screen.getByRole("button", { name: "Next page" }));
        expect(onPageChange).toHaveBeenCalledWith(4);
        fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
        expect(onPageChange).toHaveBeenCalledWith(2);
      });

      it("asks for page 1 and updates the shared size when the size changes", async () => {
        const onPageChange = vi.fn();
        render(
          <EntityListTable
            data={many(20)}
            columns={nameColumns}
            searchTerm=""
            pagination={{ total: 134, page: 3, pageSize: 20, onPageChange }}
          />,
        );
        await act(async () => {
          await userEvent.selectOptions(
            screen.getByLabelText("Rows per page"),
            "80",
          );
        });
        expect(onPageChange).toHaveBeenCalledWith(1);
        expect(window.localStorage.getItem("mlflow-oidc-auth:page-size")).toBe(
          "80",
        );
      });
    });
  });
});
