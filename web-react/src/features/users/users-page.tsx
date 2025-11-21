import { useState, type FormEvent } from "react";
import { SearchInput } from "../../shared/components/search-input";

// Mock user data
const ALL_USERS = [
  { id: 1, name: "Alice Johnson" },
  { id: 2, name: "Bob Smith" },
  { id: 3, name: "Charlie Brown" },
  { id: 4, name: "David Lee" },
  { id: 5, name: "Amy Wilson" },
  { id: 6, name: "Alice Johnson" },
  { id: 7, name: "Bob Smith" },
  { id: 8, name: "Charlie Brown" },
  { id: 9, name: "David Lee" },
  { id: 10, name: "Amy Wilson" },
  { id: 11, name: "Alice Johnson" },
  { id: 12, name: "Bob Smith" },
  { id: 13, name: "Charlie Brown" },
  { id: 14, name: "David Lee" },
  { id: 15, name: "Amy Wilson" },
];

export default function UsersPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [submittedTerm, setSubmittedTerm] = useState("");

  const filteredUsers = ALL_USERS.filter((user) =>
    user.name.toLowerCase().includes(submittedTerm.toLowerCase())
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

      <h3 className="text-xl font-medium mb-2">
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
          {filteredUsers.map((user) => (
            <div
              key={user.id}
              role="row"
              className="p-1 border-b 
              border-btn-secondary-border dark:border-btn-secondary-border-dark"
            >
              {user.name}
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
