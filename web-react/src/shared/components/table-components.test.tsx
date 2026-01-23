import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TableEmptyState } from "./table-empty-state";
import { TableHeader } from "./table-header";
import { TableFooter } from "./table-footer";
import { PrimitiveTableRow, ObjectTableRow } from "./table-rows";

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

  describe("PrimitiveTableRow", () => {
    it("renders value", () => {
      // Mock console.log
      const logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
      render(<PrimitiveTableRow value="Test Value" index={0} />);

      expect(screen.getByText("Test Value")).toBeInTheDocument();

      fireEvent.click(screen.getByText("Test Value"));
      expect(logSpy).toHaveBeenCalledWith("row-click:", "Test Value");
      logSpy.mockRestore();
    });
  });

  describe("ObjectTableRow", () => {
      it("renders row cells", () => {
          const item = { id: "1", name: "Test" };
          const columns = [
              { header: "Name", accessorKey: "name", render: (i: any) => i.name },
          ];
          render(<ObjectTableRow item={item} columns={columns} index={0} fallbackKey={0} />);
          expect(screen.getByText("Test")).toBeInTheDocument();
      });
  });
});
