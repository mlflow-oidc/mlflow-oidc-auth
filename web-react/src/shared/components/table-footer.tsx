import { useId } from "react";
import {
  faAnglesLeft,
  faAnglesRight,
  faChevronLeft,
  faChevronRight,
} from "@fortawesome/free-solid-svg-icons";
import { Button } from "./button";
import {
  PAGE_SIZE_OPTIONS,
  parsePageSize,
} from "../../core/hooks/use-page-size";
import type { PageSize } from "../types/table";
import { formatRangeLabel, getPageCount } from "../utils/pagination";

export interface TableFooterProps {
  /** Number of items across all pages. */
  total: number;
  /** Current page, 1-based. */
  page: number;
  pageSize: PageSize;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: PageSize) => void;
}

const optionLabel = (size: PageSize) => (size === "all" ? "All" : String(size));

export function TableFooter({
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: TableFooterProps) {
  const selectId = useId();
  const pageCount = getPageCount(total, pageSize);
  const current = Math.min(Math.max(page, 1), pageCount);
  const isFirst = current <= 1;
  const isLast = current >= pageCount;

  const handlePageSizeChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    const next = parsePageSize(event.target.value);
    if (next === null) return;
    onPageSizeChange(next);
    onPageChange(1);
  };

  return (
    <nav
      id="pagination-footer"
      aria-label="Pagination"
      className="flex-shrink-0 flex flex-wrap items-center justify-end gap-x-4 gap-y-2 pt-2 text-sm
        text-text-primary dark:text-text-primary-dark"
    >
      <div className="flex items-center gap-2">
        <label htmlFor={selectId} className="whitespace-nowrap">
          Rows per page
        </label>
        <select
          id={selectId}
          value={String(pageSize)}
          onChange={handlePageSizeChange}
          className="px-2 py-1 border rounded-md focus:outline-none cursor-pointer
            text-ui-text dark:text-ui-text-dark
            bg-ui-bg dark:bg-ui-bg-dark
            border-ui-border dark:border-ui-border-dark
            focus:border-btn-primary dark:focus:border-btn-primary-dark
            focus-visible:border-btn-primary dark:focus-visible:border-btn-primary-dark"
        >
          {PAGE_SIZE_OPTIONS.map((size) => (
            <option key={String(size)} value={String(size)}>
              {optionLabel(size)}
            </option>
          ))}
        </select>
      </div>

      <span
        data-testid="pagination-range"
        aria-live="polite"
        className="tabular-nums whitespace-nowrap"
      >
        {formatRangeLabel(total, current, pageSize)}
      </span>

      {pageCount > 1 && (
        <div className="flex items-center gap-1">
          <Button
            icon={faAnglesLeft}
            aria-label="First page"
            title="First page"
            className="w-7 h-7"
            disabled={isFirst}
            onClick={() => onPageChange(1)}
          />
          <Button
            icon={faChevronLeft}
            aria-label="Previous page"
            title="Previous page"
            className="w-7 h-7"
            disabled={isFirst}
            onClick={() => onPageChange(current - 1)}
          />
          <Button
            icon={faChevronRight}
            aria-label="Next page"
            title="Next page"
            className="w-7 h-7"
            disabled={isLast}
            onClick={() => onPageChange(current + 1)}
          />
          <Button
            icon={faAnglesRight}
            aria-label="Last page"
            title="Last page"
            className="w-7 h-7"
            disabled={isLast}
            onClick={() => onPageChange(pageCount)}
          />
        </div>
      )}
    </nav>
  );
}
