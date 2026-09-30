import { useState } from "react";
import { TableHeader } from "./table-header";
import { TableEmptyState } from "./table-empty-state";
import { TableFooter } from "./table-footer";
import { getPageCount } from "../utils/pagination";
import type { Identifiable, EntityListTableProps } from "../types/table";
import { ObjectTableRow } from "./table-rows";
import { usePageSize } from "../../core/hooks/use-page-size";

/**
 * A list table with a pagination footer.
 *
 * Client mode (no `pagination` prop): `data` is the whole (already filtered) list and the table
 * shows one page of it. The page resets to 1 when `searchTerm` or the page size changes and is
 * clamped when `data` shrinks below it.
 *
 * Server mode (`pagination` given): `data` is already the current page; the footer uses
 * `pagination.total` and reports page changes through `pagination.onPageChange`.
 */
export function EntityListTable<
  T extends Identifiable & Record<string, unknown>,
>(props: EntityListTableProps<T>) {
  const { data, columns, searchTerm, getRowHref, pagination } = props;
  const { pageSize: preferredPageSize, setPageSize } = usePageSize();

  // Client-mode page, keyed so a new search or page size starts at page 1.
  const resetKey = `${String(preferredPageSize)}\u0000${searchTerm}`;
  const [clientPage, setClientPage] = useState({ key: resetKey, page: 1 });

  let rows = data;
  let total: number;
  let page: number;
  let pageSize = preferredPageSize;
  let onPageChange: (page: number) => void;

  if (pagination) {
    total = pagination.total;
    page = pagination.page;
    pageSize = pagination.pageSize;
    onPageChange = pagination.onPageChange;
  } else {
    total = data.length;
    const pageCount = getPageCount(total, pageSize);
    const requested = clientPage.key === resetKey ? clientPage.page : 1;
    page = Math.min(requested, pageCount);
    if (pageSize !== "all") {
      rows = data.slice((page - 1) * pageSize, page * pageSize);
    }
    onPageChange = (next) =>
      setClientPage({
        key: resetKey,
        page: Math.min(Math.max(next, 1), pageCount),
      });
  }

  return (
    <div role="table" className="flex flex-col flex-1 overflow-hidden text-sm">
      <TableHeader columns={columns} hasRowChevron={!!getRowHref} />

      <div role="rowgroup" className="flex-1 overflow-y-auto">
        {rows.length > 0 ? (
          rows.map((item, i) => (
            <ObjectTableRow
              key={item.id ?? i}
              item={item}
              columns={columns}
              fallbackKey={i}
              index={i}
              getRowHref={getRowHref}
            />
          ))
        ) : (
          <TableEmptyState searchTerm={searchTerm} />
        )}
      </div>

      <TableFooter
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={onPageChange}
        onPageSizeChange={setPageSize}
      />
    </div>
  );
}
