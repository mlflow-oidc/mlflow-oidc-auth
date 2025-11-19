import React, {
  type InputHTMLAttributes,
  type FormEvent,
  useCallback,
} from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faSearch, faTimes } from "@fortawesome/free-solid-svg-icons";

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
      className="flex h-8 rounded border border-text-primary-hover dark:border-text-primary-hover-dark bg-ui-bg dark:bg-ui-bg-dark overflow-hidden"
      style={{ minWidth: "100px", maxWidth: "300px" }}
    >
      <input
        type="text"
        value={value}
        onChange={onInputChange}
        placeholder={placeholder}
        name="searchTerm"
        className={`flex-grow min-w-0 px-3 py-1 text-ui-text dark:text-ui-text-dark bg-ui-bg dark:bg-ui-bg-dark placeholder-text-primary dark:placeholder-text-primary-dark focus:outline-none ${
          showClearButton ? "pr-1" : "pr-3"
        }`}
        {...rest}
      />

      {showClearButton && (
        <button
          type="button"
          onClick={handleClear}
          title="Clear search"
          className="h-full w-8 flex-shrink-0 flex items-center justify-center text-text-primary hover:text-btn-secondary-text-hover dark:text-text-primary-dark dark:hover:text-btn-secondary-text-hover-dark focus:outline-none cursor-pointer"
        >
          <FontAwesomeIcon icon={faTimes} size="sm" />
        </button>
      )}

      <button
        type="submit"
        title="Search"
        className="h-full w-8 flex-shrink-0 flex items-center justify-center border-l border-text-primary-hover dark:border-text-primary-hover-dark text-text-primary dark:text-text-primary-dark hover:bg-bg-primary-hover dark:hover:bg-bg-primary-hover-dark focus:outline-none cursor-pointer"
      >
        <FontAwesomeIcon icon={faSearch} size="sm" />
      </button>
    </form>
  );
};
