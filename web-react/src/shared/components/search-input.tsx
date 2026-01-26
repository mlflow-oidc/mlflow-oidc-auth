import React, {
  type InputHTMLAttributes,
  type FormEvent,
  useCallback,
} from "react";
import { faSearch, faTimes } from "@fortawesome/free-solid-svg-icons";
import { Button } from "./button";

type InputPassThroughProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "onChange" | "onSubmit" | "onClear" | "placeholder"
>;

interface SearchInputProps extends InputPassThroughProps {
  value: string;
  onInputChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClear: () => void;
  placeholder?: string;
}

export const SearchInput: React.FC<SearchInputProps> = ({
  value,
  onInputChange,
  onSubmit,
  onClear,
  placeholder = "Search...",
  ...rest
}) => {
  const showClearButton = value.length > 0;

  const handleClear = useCallback(() => {
    onClear();
  }, [onClear]);

  return (
    <form
      onSubmit={onSubmit}
      className="shrink-0 flex h-8 rounded border text-sm mb-1 mt-2
      border-text-primary-hover dark:border-text-primary-hover-dark
      bg-ui-bg dark:bg-ui-bg-dark overflow-hidden relative"
      style={{ minWidth: "100px", maxWidth: "250px" }}
    >
      <input
        type="text"
        value={value}
        onChange={onInputChange}
        placeholder={placeholder}
        name="searchTerm"
        className={`grow min-w-0 px-3 py-1 text-ui-text dark:text-ui-text-dark bg-ui-bg
          dark:bg-ui-bg-dark placeholder-text-primary dark:placeholder-text-primary-dark focus:outline-none pr-8`}
        {...rest}
      />

      {showClearButton && (
        <Button
          variant="ghost"
          onClick={handleClear}
          title="Clear search"
          className="h-full w-8 rounded-none shrink-0 hover:bg-transparent dark:hover:bg-transparent hover:text-btn-secondary-text-hover dark:hover:text-btn-secondary-text-hover-dark absolute right-8 top-0"
          icon={faTimes}
        />
      )}

      <Button
        type="submit"
        title="Search"
        variant="ghost"
        className="h-full w-8 rounded-none border-l border-text-primary-hover dark:border-text-primary-hover-dark"
        icon={faSearch}
      />
    </form>
  );
};
