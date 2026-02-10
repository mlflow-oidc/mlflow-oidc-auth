import { TableHeader } from "./table-header";
import { TableEmptyState } from "./table-empty-state";
import { TableFooter } from "./table-footer";
import type { Identifiable, EntityListTableProps } from "../types/table";
import { ObjectTableRow } from "./table-rows";

export function EntityListTable<
  T extends Identifiable & Record<string, unknown>,
>(props: EntityListTableProps<T>) {
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
