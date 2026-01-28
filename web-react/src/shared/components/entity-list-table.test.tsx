import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { EntityListTable } from "./entity-list-table";
import type { ColumnConfig } from "../types/table";

describe("EntityListTable", () => {
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
});
