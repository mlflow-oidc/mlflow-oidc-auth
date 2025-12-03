export type ColumnConfig<T extends Record<string, unknown>> = {
  header: string;
  render: (item: T) => React.ReactNode;
  className?: string;
};

export type Identifiable = { id?: string | number };

export type EntityListTableProps<
  T extends Identifiable & Record<string, unknown>
> = {
  data: T[];
  columns: ColumnConfig<T>[];
  searchTerm: string;
};

export function EntityListTable<
  T extends Identifiable & Record<string, unknown>
>({ data, columns, searchTerm }: EntityListTableProps<T>) {
  return (
    <div role="table" className="flex flex-col flex-1 overflow-hidden">
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
              className={`p-2 flex-1 min-w-0 ${column.className || ""}`}
            >
              {column.header}
            </div>
          ))}
        </div>
      </div>

      <div role="rowgroup" className="flex-1 overflow-y-auto">
        {data.length > 0 ? (
          data.map((item, itemIndex) => (
            <div
              key={item.id || itemIndex}
              role="row"
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
          ))
        ) : (
          <p className="text-btn-secondary-text dark:text-btn-secondary-text-dark italic p-4">
            No items found for "{searchTerm}"
          </p>
        )}
      </div>

      <div
        id="pagination-footer"
        className="flex-shrink-0 italic text-right pt-2"
      >
        placeholder for pagination
      </div>
    </div>
  );
}
