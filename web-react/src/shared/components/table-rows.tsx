import type { Identifiable, ObjectTableRowProps } from "../types/table";

export function PrimitiveTableRow({
  value,
  index,
}: {
  value: string;
  index: number;
}) {
  const handleClick = () => {
    console.log("row-click:", value);
  };
  return (
    <div
      role="row"
      key={index}
      onClick={handleClick}
      className="flex border-b 
              border-btn-secondary-border dark:border-btn-secondary-border-dark
              hover:bg-table-row-hover dark:hover:bg-table-row-hover"
    >
      <div role="cell" className="p-1 flex-1 min-w-0 truncate">
        {value}
      </div>
    </div>
  );
}

export function ObjectTableRow<
  T extends Identifiable & Record<string, unknown>
>(props: ObjectTableRowProps<T>) {
  const { item, columns, fallbackKey } = props;

  const key = item.id ?? fallbackKey;
  return (
    <div
      key={key}
      role="row"
      className="flex items-center border-b group
              border-btn-secondary-border dark:border-btn-secondary-border-dark
              hover:bg-table-row-hover dark:hover:bg-table-row-hover "
    >
      {columns.map((column) => (
        <div
          key={column.header}
          role="cell"
          className={`p-1 flex-1 min-w-0 truncate ${column.className || ""}`}
        >
          {column.render(item)}
        </div>
      ))}
    </div>
  );
}
