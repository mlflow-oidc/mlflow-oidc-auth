import React, { useId, useMemo, useRef, useState } from "react";

/** How many matches are listed at once; a large directory is narrowed by typing. */
const MAX_SHOWN = 100;

interface SearchableSelectProps {
  id: string;
  label: string;
  options: string[];
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
  isLoading?: boolean;
  emptyText?: string;
}

/**
 * A text box that filters `options` as you type, with the matches in a list below it
 * (WAI-ARIA combobox). Arrow keys move through the matches, Enter picks one, Escape closes the
 * list without closing the dialog around it. Options are rendered as text.
 */
export function SearchableSelect({
  id,
  label,
  options,
  value,
  onChange,
  placeholder,
  isLoading = false,
  emptyText = "No matches",
}: SearchableSelectProps) {
  const listId = useId();
  const [query, setQuery] = useState(value ?? "");
  const [isOpen, setIsOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const { matches, truncated } = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const found = needle
      ? options.filter((o) => o.toLowerCase().includes(needle))
      : options;
    return {
      matches: found.slice(0, MAX_SHOWN),
      truncated: found.length > MAX_SHOWN,
    };
  }, [options, query]);

  const pick = (option: string) => {
    onChange(option);
    setQuery(option);
    setIsOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setIsOpen(true);
      setActive((i) => Math.min(i + 1, Math.max(matches.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      if (isOpen && matches[active]) {
        e.preventDefault();
        pick(matches[active]);
      }
    } else if (e.key === "Escape" && isOpen) {
      // Close the list only; the dialog around it stays open.
      e.preventDefault();
      e.stopPropagation();
      setIsOpen(false);
    }
  };

  const activeId =
    isOpen && matches[active] ? `${listId}-option-${active}` : undefined;

  return (
    <div className="relative mb-3">
      <label
        htmlFor={id}
        className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1"
      >
        {label}
      </label>
      <input
        ref={inputRef}
        id={id}
        type="text"
        role="combobox"
        aria-expanded={isOpen}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        autoComplete="off"
        value={query}
        placeholder={isLoading ? "Loading..." : placeholder}
        disabled={isLoading}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setIsOpen(true);
          if (value !== null && e.target.value !== value) onChange(null);
        }}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setIsOpen(false)}
        onKeyDown={handleKeyDown}
        className="w-full px-3 py-2 border rounded-md focus:outline-none text-ui-text dark:text-ui-text-dark bg-ui-bg dark:bg-ui-bg-dark border-ui-border dark:border-ui-border-dark focus:border-btn-primary dark:focus:border-btn-primary-dark disabled:opacity-70"
      />
      {isOpen && !isLoading && (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto rounded-md shadow-lg border border-ui-border dark:border-ui-border-dark bg-ui-bg dark:bg-ui-bg-dark text-sm"
        >
          {matches.length === 0 && (
            <li className="px-3 py-2 text-ui-text-muted dark:text-ui-text-muted-dark">
              {emptyText}
            </li>
          )}
          {matches.map((option, index) => (
            <li
              key={option}
              id={`${listId}-option-${index}`}
              role="option"
              aria-selected={option === value}
              // mousedown, not click: it lands before the input's blur closes the list.
              onMouseDown={(e) => {
                e.preventDefault();
                pick(option);
              }}
              onMouseEnter={() => setActive(index)}
              className={`px-3 py-1.5 cursor-pointer font-mono break-all ${
                index === active
                  ? "bg-bg-primary-hover dark:bg-bg-primary-hover-dark"
                  : ""
              } text-ui-text dark:text-ui-text-dark`}
            >
              {option}
            </li>
          ))}
          {truncated && (
            <li className="px-3 py-1.5 text-xs text-ui-text-muted dark:text-ui-text-muted-dark">
              Showing the first {MAX_SHOWN} matches — type to narrow.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
