import type { Identifiable, ObjectTableRowProps } from "../types/table";


export function ObjectTableRow<
  T extends Identifiable & Record<string, unknown>,
>(props: ObjectTableRowProps<T>) {
  const { item, columns, fallbackKey } = props;

  const key = item.id ?? fallbackKey;
  return (
    <div
      key={key}
      role="row"
      className="flex items-center h-(--table-row-height) border-b group
              border-btn-secondary-border dark:border-btn-secondary-border-dark
              hover:bg-table-row-hover dark:hover:bg-table-row-hover "
    >
      {columns.map((column, index) => (
        <div
          key={
            column.id ||
            (typeof column.header === "string" ? column.header : index)
          }
          role="cell"
          className={`px-1 flex-1 min-w-0 truncate ${column.className || ""}`}
        >
          {column.render(item)}
        </div>
      ))}
    </div>
  );
}
