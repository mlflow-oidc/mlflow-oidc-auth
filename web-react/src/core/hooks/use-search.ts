import { useState, type FormEvent, useCallback } from "react";

export function useSearch() {
  const [searchTerm, setSearchTerm] = useState("");
  const [submittedTerm, setSubmittedTerm] = useState("");

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setSearchTerm(event.target.value);
    },
    []
  );

  const handleSearchSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setSubmittedTerm(searchTerm);
    },
    [searchTerm]
  );

  const handleClearSearch = useCallback(() => {
    setSearchTerm("");
    setSubmittedTerm("");
  }, []);

  return {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  };
}
