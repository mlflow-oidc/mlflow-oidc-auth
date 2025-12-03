import { useState, type FormEvent } from "react";
import { SearchInput } from "../../shared/components/search-input";
import { useAllExperiments } from "../../core/hooks/use-all-experiments";
import {
  EntityListTable,
  type ColumnConfig,
} from "../../shared/components/entity-list-table";
import type { ExperimentListItem } from "../../shared/types/entity";

const experimentColumns: ColumnConfig<ExperimentListItem>[] = [
  {
    header: "ID",
    render: (item) => item.id,
  },
  {
    header: "Experiment Name",
    render: (item) => item.name,
  },
  {
    header: "Tags",
    render: (item) =>
      Object.entries(item.tags)
        .map(([key, value]) => `${key}: ${value}`)
        .join(", "),
  },
];

export default function ExperimentsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [submittedTerm, setSubmittedTerm] = useState("");

  const { isLoading, error, refresh, allExperiments } = useAllExperiments(true);

  const experimentsList = allExperiments || [];

  console.log("ExperimentsList:", experimentsList);
  const filteredExperiments = experimentsList.filter((experiment) =>
    experiment.name.toLowerCase().includes(submittedTerm.toLowerCase())
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
          Loading experiments list...
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
        Experiments Page
      </h2>

      <SearchInput
        value={searchTerm}
        onInputChange={handleInputChange}
        onSubmit={handleSearchSubmit}
        onClear={handleClearSearch}
        placeholder="Search experiments..."
      />

      <h3 className="text-base font-medium p-1 mb-1">
        Results ({filteredExperiments.length})
      </h3>

      <EntityListTable
        data={filteredExperiments}
        columns={experimentColumns}
        searchTerm={submittedTerm}
      />
    </>
  );
}
