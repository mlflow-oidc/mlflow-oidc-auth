import React from "react";
import { Link } from "react-router";

interface EntityNameLinkProps {
  /** In-app router path, e.g. from `buildEntityRoute`. */
  to: string;
  children: React.ReactNode;
  /** Full value for the tooltip when the text is truncated. */
  title?: string;
  className?: string;
}

/**
 * The entity name cell of a list table, rendered as a real link so the
 * row's destination is reachable by keyboard, screen readers and touch.
 * Pair it with `EntityListTable`'s `getRowHref` so the whole row is a
 * mouse target for the same destination.
 */
export function EntityNameLink({
  to,
  children,
  title,
  className = "",
}: EntityNameLinkProps) {
  return (
    <Link
      to={to}
      title={title}
      className={`truncate block rounded-sm
        text-btn-primary dark:text-btn-primary-dark
        hover:underline focus-visible:underline
        focus-visible:outline-2 focus-visible:outline-offset-1
        focus-visible:outline-btn-primary dark:focus-visible:outline-btn-primary-dark
        ${className}`
        .replace(/\s+/g, " ")
        .trim()}
    >
      {children}
    </Link>
  );
}
