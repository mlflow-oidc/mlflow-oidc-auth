import type { ColumnConfig } from "../types/table";

export function TableHeader<T extends Record<string, unknown>>({
  columns,
}: {
  columns: ColumnConfig<T>[];
}) {
  return (
    <div role="rowgroup" className="shrink-0">
      <div
        role="row"
        className="flex items-center h-(--table-row-height) border-b
          border-btn-secondary-border dark:border-btn-secondary-border-dark
          font-semibold text-left"
      >
        {columns.map((column, index) => (
          <div
            key={
              column.id ||
              (typeof column.header === "string" ? column.header : index)
            }
            role="columnheader"
            className={`px-1 flex-1 min-w-0 truncate ${column.className || ""}`}
          >
            {column.header}
          </div>
        ))}
      </div>
    </div>
  );
}
