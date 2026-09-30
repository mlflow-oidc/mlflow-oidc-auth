import type { PageSize } from "../types/table";

/** Number of pages for `total` items; at least 1 so an empty list is "page 1 of 1". */
export function getPageCount(total: number, pageSize: PageSize): number {
  if (pageSize === "all" || total <= 0) return 1;
  return Math.ceil(total / pageSize);
}

/**
 * The range label, e.g. "1–20 of 134", "0 of 0" when empty, "All 134" when every row is shown.
 */
export function formatRangeLabel(
  total: number,
  page: number,
  pageSize: PageSize,
): string {
  if (total <= 0) return "0 of 0";
  if (pageSize === "all") return `All ${total}`;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return `${start}–${end} of ${total}`;
}
