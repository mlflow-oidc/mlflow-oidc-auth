import { useState, type FormEvent } from "react";
import { SearchInput } from "../../shared/components/search-input";

// Mock user data
const ALL_USERS = [
  { id: 1, name: "Alice Johnson" },
  { id: 2, name: "Bob Smith" },
  { id: 3, name: "Charlie Brown" },
  { id: 4, name: "David Lee" },
  { id: 5, name: "Amy Wilson" },
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
      <h2 className="text-3xl font-semibold mb-6 text-center">Users Page</h2>
      <SearchInput
        value={searchTerm}
        onInputChange={handleInputChange}
        onSubmit={handleSearchSubmit}
        onClear={handleClearSearch}
        placeholder="Search users..."
      />
      <div className="mt-8">
        <h3 className="text-xl font-medium mb-3">
          Results ({filteredUsers.length})
        </h3>
        {filteredUsers.map((user) => (
          <div key={user.id} className="p-2 border-b">
            {user.name}
          </div>
        ))}
        {filteredUsers.length === 0 && (
          <p className="text-gray-500 italic">
            No users found for "{submittedTerm}"
          </p>
        )}
      </div>
    </>
  );
}
