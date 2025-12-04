import type { Identifiable, ColumnConfig } from "../types/table";

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
      className="flex border-b text-base
              border-btn-secondary-border dark:border-btn-secondary-border-dark
              hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
    >
      <div role="cell" className="p-2 flex-1 min-w-0">
        {value}
      </div>
    </div>
  );
}

export function ObjectTableRow<
  T extends Identifiable & Record<string, unknown>
>({
  item,
  columns,
  fallbackKey,
}: {
  item: T;
  columns: ColumnConfig<T>[];
  fallbackKey: string | number;
}) {
  const key = item.id ?? fallbackKey;

  const handleClick = () => {
    console.log("row-click:", item.id ?? key);
  };

  return (
    <div
      key={key}
      role="row"
      onClick={handleClick}
      className="flex border-b text-base
              border-btn-secondary-border dark:border-btn-secondary-border-dark
              hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
    >
      {columns.map((column) => (
        <div
          key={column.header}
          role="cell"
          className={`p-2 flex-1 min-w-0 ${column.className || ""}`}
        >
          {column.render(item)}
        </div>
      ))}
    </div>
  );
}
