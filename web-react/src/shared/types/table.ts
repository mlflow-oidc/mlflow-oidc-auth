export type ColumnConfig<T extends Record<string, unknown>> = {
  header: React.ReactNode;
  id?: string;
  render: (item: T) => React.ReactNode;
  className?: string;
};

export type Identifiable = { id?: string | number };

/** Rows per page offered by list tables; `"all"` renders every row. */
export type PageSize = 20 | 40 | 80 | "all";

/**
 * Server-side pagination state for {@link EntityListTableProps.pagination}.
 * `page` is 1-based.
 */
export interface TablePagination {
  /** Number of items matching the current search across all pages. */
  total: number;
  page: number;
  pageSize: PageSize;
  onPageChange: (page: number) => void;
}

export type EntityListTableProps<
  T extends Identifiable & Record<string, unknown>,
> = {
  data: T[];
  columns: ColumnConfig<T>[];
  searchTerm: string;
  /**
   * Makes each row a mouse target for this in-app route: the row gets a
   * pointer cursor, a trailing chevron, and navigates on click (clicks on
   * buttons, links and form controls inside the row are left alone).
   * Keyboard and screen-reader access must come from a real link in a cell,
   * typically `EntityNameLink` pointing at the same route.
   */
  getRowHref?: (item: T) => string;
  /**
   * Server mode: `data` is already the current page and `total` counts every
   * matching item. Omit for client mode, where the table slices `data` itself
   * using the shared rows-per-page preference.
   */
  pagination?: TablePagination;
};

export interface ObjectTableRowProps<
  T extends Identifiable & Record<string, unknown>,
> {
  item: T;
  columns: ColumnConfig<T>[];
  fallbackKey: string | number;
  index: number;
  /** See `EntityListTableProps.getRowHref`. */
  getRowHref?: (item: T) => string;
}
