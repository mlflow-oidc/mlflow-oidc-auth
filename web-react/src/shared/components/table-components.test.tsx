import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TableEmptyState } from "./table-empty-state";
import { TableHeader } from "./table-header";
import { TableFooter } from "./table-footer";
import { ObjectTableRow } from "./table-rows";
import type { ColumnConfig } from "../types/table";

describe("Table Components", () => {
  describe("TableEmptyState", () => {
    it("renders default message", () => {
      render(<TableEmptyState searchTerm="" />);
      expect(screen.getByText("No items found")).toBeInTheDocument();
    });

    it("renders search message", () => {
      render(<TableEmptyState searchTerm="xyz" />);
      expect(screen.getByText('No items found for "xyz"')).toBeInTheDocument();
    });
  });

  describe("TableHeader", () => {
    it("renders columns", () => {
      const columns = [
        { header: "Col 1", render: () => null },
        { header: "Col 2", render: () => null },
      ];
      render(<TableHeader columns={columns} />);
      expect(screen.getByText("Col 1")).toBeInTheDocument();
      expect(screen.getByText("Col 2")).toBeInTheDocument();
    });
  });

  describe("TableFooter", () => {
    it("renders footer", () => {
      render(<TableFooter />);
      expect(screen.getByText(/placeholder/)).toBeInTheDocument();
    });
  });

  describe("ObjectTableRow", () => {
    it("renders row cells", () => {
      interface MockItem extends Record<string, unknown> {
        id: string;
        name: string;
      }
      const item: MockItem = { id: "1", name: "Test" };
      const columns: ColumnConfig<MockItem>[] = [
        { header: "Name", id: "name", render: (i) => i.name },
      ];
      render(
        <ObjectTableRow
          item={item}
          columns={columns}
          index={0}
          fallbackKey={0}
        />,
      );
      expect(screen.getByText("Test")).toBeInTheDocument();
    });
  });
});
