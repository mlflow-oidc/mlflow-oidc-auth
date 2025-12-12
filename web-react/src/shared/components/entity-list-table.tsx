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
      <div
        role="table"
        className="flex flex-col flex-1 overflow-hidden text-sm"
      >
        <div role="rowgroup" className="flex-shrink-0">
          <div
            role="row"
            className="flex border-b font-semibold text-left
                    border-btn-secondary-border dark:border-btn-secondary-border-dark"
          >
            <div role="columnheader" className="p-1 flex-1 min-w-0">
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
    <div role="table" className="flex flex-col flex-1 overflow-hidden text-sm">
      <TableHeader columns={columns} />

      <div role="rowgroup" className="flex-1 overflow-y-auto">
        {data.length > 0 ? (
          data.map((item, i) => (
            <ObjectTableRow
              key={item.id ?? i}
              item={item}
              columns={columns}
              fallbackKey={i}
              index={i}
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
