import type { ColumnConfig } from "../types/table";

export function TableHeader<T extends Record<string, unknown>>({
  columns,
}: {
  columns: ColumnConfig<T>[];
}) {
  return (
    <div role="rowgroup" className="flex-shrink-0">
      <div
        role="row"
        className="flex border-b
          border-btn-secondary-border dark:border-btn-secondary-border-dark
          font-semibold text-left"
      >
        {columns.map((column) => (
          <div
            key={column.header}
            role="columnheader"
            className={`p-1 flex-1 min-w-0 ${column.className || ""}`}
          >
            {column.header}
          </div>
        ))}
      </div>
    </div>
  );
}
