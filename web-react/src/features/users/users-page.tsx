import { useState, type FormEvent } from "react";
import { SearchInput } from "../../shared/components/search-input";
import { useAllUsers } from "../../core/hooks/use-all-users";

export default function UsersPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [submittedTerm, setSubmittedTerm] = useState("");

  const { isLoading, error, refresh, allUsers } = useAllUsers(true);

  const usersList = allUsers || [];

  const filteredUsers = usersList.filter((username) =>
    username.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  };

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setSubmittedTerm(searchTerm);
    console.log(`Submitting search for: "${searchTerm}"."`);
  };

  const handleClearSearch = () => {
    setSearchTerm("");
    setSubmittedTerm("");
    console.log("Search cleared. Showing full list.");
  };

  if (isLoading) {
    return (
      <div className="flex h-full justify-center items-center p-8">
        <p className="text-lg font-medium animate-pulse text-text-primary dark:text-text-primary-dark">
          Loading users list...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-wrap h-full justify-center content-center items-center gap-2 text-red-600">
        <p className="text-xl">Error fetching users: {error.message}</p>
        <button
          type="button"
          onClick={() => refresh()}
          className="ml-4 p-2 bg-red-100 rounded hover:bg-red-200 cursor-pointer"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <>
      <h2 className="flex-shrink-0 text-3xl font-semibold mb-6 text-center">
        Users Page
      </h2>

      <SearchInput
        value={searchTerm}
        onInputChange={handleInputChange}
        onSubmit={handleSearchSubmit}
        onClear={handleClearSearch}
        placeholder="Search users..."
      />

      <h3 className="text-base font-medium p-1 mb-1">
        Results ({filteredUsers.length})
      </h3>

      <div role="table" className="flex flex-col flex-1 overflow-hidden">
        <div role="rowgroup" className="flex-shrink-0">
          <div
            role="row"
            className="flex border-b p-1 font-semibold
            border-btn-secondary-border dark:border-btn-secondary-border-dark"
          >
            Username
          </div>
        </div>
        <div role="rowgroup" className="flex-1 overflow-y-auto">
          {filteredUsers.map((username) => (
            <div
              key={username}
              role="row"
              className="p-2 border-b
              border-btn-secondary-border dark:border-btn-secondary-border-dark"
            >
              {username}
            </div>
          ))}
          {filteredUsers.length === 0 && (
            <p className="text-btn-secondary-text dark:text-btn-secondary-text-dark italic">
              No users found for "{submittedTerm}"
            </p>
          )}
        </div>
        <div
          id="pagination-footer"
          className="flex-shrink-0 italic text-right pt-2"
        >
          placeholder for pagination
        </div>
      </div>
    </>
  );
}
