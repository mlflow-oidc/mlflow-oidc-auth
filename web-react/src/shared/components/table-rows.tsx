import React from "react";
import { useNavigate } from "react-router";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faChevronRight } from "@fortawesome/free-solid-svg-icons";
import type {
  ColumnConfig,
  Identifiable,
  ObjectTableRowProps,
} from "../types/table";

/**
 * Clicks that start on (or inside) one of these belong to that control, not
 * to the row, so they must never trigger row navigation.
 */
const INTERACTIVE_SELECTOR = [
  "a",
  "button",
  "input",
  "select",
  "textarea",
  "label",
  "[role='button']",
  "[role='link']",
  "[role='switch']",
  "[role='checkbox']",
  "[role='menuitem']",
  "[contenteditable='true']",
].join(",");

const ROW_BASE_CLASSES = `flex items-center h-(--table-row-height) border-b group
  border-btn-secondary-border dark:border-btn-secondary-border-dark
  hover:bg-table-row-hover dark:hover:bg-table-row-hover-dark`;

function RowCells<T extends Identifiable & Record<string, unknown>>({
  item,
  columns,
}: {
  item: T;
  columns: ColumnConfig<T>[];
}) {
  return (
    <>
      {columns.map((column, index) => (
        <div
          key={
            column.id ||
            (typeof column.header === "string" ? column.header : index)
          }
          role="cell"
          className={`px-1 flex-1 min-w-0 truncate ${column.className || ""}`}
        >
          {column.render(item)}
        </div>
      ))}
    </>
  );
}

function NavigableTableRow<T extends Identifiable & Record<string, unknown>>({
  item,
  columns,
  href,
}: {
  item: T;
  columns: ColumnConfig<T>[];
  href: string;
}) {
  const navigate = useNavigate();

  const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target;
    if (target instanceof Element) {
      const interactive = target.closest(INTERACTIVE_SELECTOR);
      if (interactive && event.currentTarget.contains(interactive)) return;
    }
    // Don't hijack a text selection (e.g. copying a name) as a navigation.
    const selection = window.getSelection?.();
    if (selection && selection.toString().length > 0) return;

    void navigate(href);
  };

  return (
    // Mouse-only convenience: the keyboard/screen-reader path to the same
    // destination is the link rendered inside the row (see getRowHref docs),
    // so the row itself is deliberately not focusable.
    <div
      role="row"
      onClick={handleClick}
      className={`${ROW_BASE_CLASSES} cursor-pointer`}
    >
      <RowCells item={item} columns={columns} />
      <div
        aria-hidden="true"
        data-testid="row-chevron"
        className="w-6 shrink-0 flex justify-center text-xs
          text-text-primary dark:text-text-primary-dark opacity-40
          group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity"
      >
        <FontAwesomeIcon icon={faChevronRight} />
      </div>
    </div>
  );
}

export function ObjectTableRow<
  T extends Identifiable & Record<string, unknown>,
>(props: ObjectTableRowProps<T>) {
  const { item, columns, getRowHref } = props;

  if (getRowHref) {
    return (
      <NavigableTableRow
        item={item}
        columns={columns}
        href={getRowHref(item)}
      />
    );
  }

  return (
    <div role="row" className={ROW_BASE_CLASSES}>
      <RowCells item={item} columns={columns} />
    </div>
  );
}
