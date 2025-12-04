import { TableHeader } from "./table-header";
import { TableEmptyState } from "./table-empty-state";
import { TableFooter } from "./table-footer";
import type { Identifiable, EntityListTableProps } from "../types/table";
import { ObjectTableRow, PrimitiveTableRow } from "./table-rows";

export function EntityListTable<
  T extends Identifiable & Record<string, unknown>
>(props: EntityListTableProps<T>) {
  if (props.mode === "primitive") {
    const { data, searchTerm } = props;

    return (
      <div role="table" className="flex flex-col flex-1 overflow-hidden">
        <div role="rowgroup" className="flex-shrink-0">
          <div
            role="row"
            className="flex border-b
          border-btn-secondary-border dark:border-btn-secondary-border-dark
          font-semibold text-left"
          >
            <div role="columnheader" className="p-2 flex-1 min-w-0">
              Items
            </div>
          </div>
        </div>

        <div role="rowgroup" className="flex-1 overflow-y-auto">
          {data.length > 0 ? (
            data.map((value, i) => {
              const key = value + i;
              return <PrimitiveTableRow value={value} index={i} key={key} />;
            })
          ) : (
            <TableEmptyState searchTerm={searchTerm} />
          )}
        </div>

        <TableFooter />
      </div>
    );
  }

  const { data, columns, searchTerm } = props;

  return (
    <div role="table" className="flex flex-col flex-1 overflow-hidden">
      <TableHeader columns={columns} />

      <div role="rowgroup" className="flex-1 overflow-y-auto">
        {data.length > 0 ? (
          data.map((item, i) => (
            <ObjectTableRow
              key={item.id ?? i}
              item={item}
              columns={columns}
              fallbackKey={i}
            />
          ))
        ) : (
          <TableEmptyState searchTerm={searchTerm} />
        )}
      </div>

      <TableFooter />
    </div>
  );
}
